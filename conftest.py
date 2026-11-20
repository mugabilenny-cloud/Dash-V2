import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DASH_DB"] = os.path.join(_tmp, "test.db")
os.environ["DASH_PW_HAYAT"] = "testpw"
