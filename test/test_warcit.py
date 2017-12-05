import shutil
import tempfile
import os
import sys
import zipfile

from contextlib import contextmanager
from io import BytesIO
from warcit.warcit import main
from warcio.cli import main as warcio_main


# ============================================================================
@contextmanager
def patch_stream(stream=sys.stderr):
    buff = BytesIO()
    if hasattr(stream, 'buffer'):
        orig = stream.buffer
        stream.buffer = buff
        yield buff
        stream.buffer = orig
    else:
        orig = stream
        stream = buff
        yield buff
        stream = orig


# ============================================================================
class TestWarcIt(object):
    @classmethod
    def setup_class(cls):
        cls.root_dir = os.path.realpath(tempfile.mkdtemp())
        cls.orig_cwd = os.getcwd()
        os.chdir(cls.root_dir)

        root = os.path.dirname(os.path.realpath(__file__))

        cls.zip_filename = os.path.join(root, 'www.iana.org.zip')

        with zipfile.ZipFile(cls.zip_filename) as zp:
            zp.extractall()

        cls.test_dir = os.path.join(cls.root_dir, 'www.iana.org')

    @classmethod
    def teardown_class(cls):
        os.chdir(cls.orig_cwd)
        shutil.rmtree(cls.root_dir)

    def test_warcit_new(self):
        with patch_stream() as buff:
            res = main(['http://www.iana.org/', self.test_dir])
            assert res == 0

        assert 'Wrote 24 resources to www.iana.org.warc.gz' in buff.getvalue().decode('utf-8')
        assert os.path.isfile(os.path.join(self.root_dir, 'www.iana.org.warc.gz'))

    def test_warcit_already_exists(self):
        with patch_stream() as buff:
            res = main(['http://www.iana.org/', '-q', self.test_dir])
            assert res == 1

        assert 'File exists' in buff.getvalue().decode('utf-8')

    def test_warcit_append(self):
        with patch_stream() as buff:
            res = main(['-a', 'http://www.iana.org/', '-q', self.test_dir])
            assert res == 0

    def test_warcit_diff_file(self):
        with patch_stream() as buff:
            res = main(['-v', '--name', 'test', '--no-gzip', 'http://www.iana.org/', self.test_dir])
            assert res == 0

        assert 'Wrote 24 resources to test.warc' in buff.getvalue().decode('utf-8')
        assert os.path.isfile(os.path.join(self.root_dir, 'test.warc'))


        with patch_stream(sys.stdout) as buff:
            warcio_main(['index', '-f', 'warc-type,warc-target-uri,warc-date', 'test.warc'])

        buff = buff.getvalue().decode('utf-8')
        assert '"warc-type": "warcinfo"' in buff
        assert '"warc-type": "revisit", "warc-target-uri": "http://www.iana.org/"' in buff

    def test_warcit_no_revisit(self):
        with patch_stream() as buff:
            res = main(['-q', '-o', '--name', 'test', '--index-files', '', '--no-gzip', 'http://www.iana.org/', self.test_dir])
            assert res == 0

        with patch_stream(sys.stdout) as buff:
            warcio_main(['index', '-f', 'warc-type,warc-target-uri,warc-date', 'test.warc'])

        buff = buff.getvalue().decode('utf-8')
        assert '"warc-type": "warcinfo"' in buff
        assert '"warc-type": "revisit", "warc-target-uri": "http://www.iana.org/"' not in buff

    def test_warcit_fixed_date(self):
        with patch_stream() as buff:
            res = main(['-q', '-n', 'test', '--no-magic', '-d', '2010-12-26T10:11:12', 'http://www.iana.org/', self.test_dir])
            assert res == 0

        with patch_stream(sys.stdout) as buff:
            warcio_main(['index', '-f', 'warc-target-uri,warc-date,content-type', 'test.warc.gz'])

        assert '"warc-target-uri": "http://www.iana.org/index.html", "warc-date": "2010-12-26T10:11:12Z", "content-type": "text/html"' in buff.getvalue().decode('utf-8')

    def test_warcit_mime_override(self):
        with patch_stream() as buff:
            res = main(['-q', '-n', 'test2', '--mime-overrides=*/index.html=custom/mime', 'http://www.iana.org/', self.test_dir])
            assert res == 0

        with patch_stream(sys.stdout) as buff:
            warcio_main(['index', '-f', 'warc-target-uri,content-type', 'test2.warc.gz'])

        buff = buff.getvalue().decode('utf-8')
        assert '"warc-target-uri": "http://www.iana.org/index.html", "content-type": "custom/mime"' in buff
        assert '"warc-target-uri": "http://www.iana.org/about/index.html", "content-type": "custom/mime"' in buff

    def test_warcit_single_file_and_no_warcinfo(self):
        with patch_stream() as buff:
            res = main(['-v', '--no-warcinfo', 'http://www.iana.org/', os.path.join(self.test_dir, 'index.html')])
            assert res == 0

        assert 'Wrote 2 resources to index.html.warc.gz' in buff.getvalue().decode('utf-8')
        assert os.path.isfile(os.path.join(self.root_dir, 'index.html.warc.gz'))

        with patch_stream(sys.stdout) as buff:
            warcio_main(['index', '-f', 'warc-type,warc-target-uri', 'index.html.warc.gz'])

        buff = buff.getvalue().decode('utf-8')
        assert '"warc-type": "warcinfo"' not in buff
        assert '"warc-target-uri": "http://www.iana.org/index.html"' in buff
        assert '"warc-target-uri": "http://www.iana.org/"' in buff

    def test_warcit_new_zip(self):
        with patch_stream() as buff:
            res = main(['-v', 'http://', self.zip_filename])
            assert res == 0

        buff = buff.getvalue().decode('utf-8')
        assert 'Wrote 24 resources to www.iana.org.zip.warc.gz' in buff
        assert 'Writing http://www.iana.org/index.html at 2017-10-17T14:30:26Z from www.iana.org/index.html' in buff
        assert os.path.isfile(os.path.join(self.root_dir, 'www.iana.org.zip.warc.gz'))

    def test_warcit_new_zip_file_path(self):
        with patch_stream() as buff:
            res = main(['-o', '-v', 'http://www.iana.org/', self.zip_filename + '/www.iana.org/'])
            assert res == 0

        buff = buff.getvalue().decode('utf-8')
        assert 'Wrote 24 resources to www.iana.org.warc.gz' in buff
        assert 'Writing http://www.iana.org/index.html at 2017-10-17T14:30:26Z from www.iana.org/index.html' in buff
        assert os.path.isfile(os.path.join(self.root_dir, 'www.iana.org.warc.gz'))

    def test_warcit_no_such_zip_prefix(self):
        with patch_stream() as buff:
            res = main(['-o', '-v', 'http://www.iana.org/', self.zip_filename + '/www.example.com/'])
            assert res == 0

        buff = buff.getvalue().decode('utf-8')
        assert 'Wrote 0 resources to www.example.com.warc.gz' in buff
        assert os.path.isfile(os.path.join(self.root_dir, 'www.example.com.warc.gz'))

    def test_warcit_no_such_file(self):
        with patch_stream() as buff:
            res = main(['-o', '-v', 'http://www.iana.org/', './foo'])
            assert res == 0

        buff = buff.getvalue().decode('utf-8')
        assert '[ERROR]: "./foo" not a valid' in buff

    def test_warcit_no_such_file_2(self):
        with patch_stream() as buff:
            res = main(['-o', '-v', 'http://www.iana.org/', self.zip_filename + '_nosuch'])
            assert res == 0

        buff = buff.getvalue().decode('utf-8')
        assert 'www.iana.org.zip_nosuch" not a valid' in buff

