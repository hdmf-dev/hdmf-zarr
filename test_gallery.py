"""Test that the Sphinx Gallery files run without warnings or errors.
See tox.ini for usage.
"""

import importlib.util
import logging
import os
import os.path
import sys
import traceback
import warnings

TOTAL = 0
FAILURES = 0
ERRORS = 0


def _import_from_file(script):
    modname = os.path.basename(script)
    spec = importlib.util.spec_from_file_location(os.path.basename(script), script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)


_pkg_resources_warning_re = "pkg_resources is deprecated as an API"

_pkg_resources_declare_warning_re = r"Deprecated call to `pkg_resources\.declare_namespace.*"

_numpy_warning_re = "numpy.ufunc size changed, may indicate binary incompatibility. Expected 216, got 192"

_distutils_warning_re = "distutils Version classes are deprecated. Use packaging.version instead."

_experimental_warning_re = (
    "The ZarrIO backend is experimental. It is under active development. "
    "The ZarrIO backend may change any time and backward compatibility is not guaranteed."
)

_user_warning_transpose = (
    "ElectricalSeries 'ElectricalSeries': The second dimension of data does not match the "
    "length of electrodes. Your data may be transposed."
)

_deprecation_warning_map = (
    "Classes in map.py should be imported from hdmf.build. Importing from hdmf.build.map will be removed "
    "in HDMF 3.0."
)

_deprecation_warning_fmt_docval_args = (
    "fmt_docval_args will be deprecated in a future version of HDMF. Instead of using fmt_docval_args, "
    "call the function directly with the kwargs. Please note that fmt_docval_args "
    "removes all arguments not accepted by the function's docval, so if you are passing kwargs that "
    "includes extra arguments and the function's docval does not allow extra arguments (allow_extra=True "
    "is set), then you will need to pop the extra arguments out of kwargs before calling the function."
)

_deprecation_warning_call_docval_func = (
    "call the function directly with the kwargs. Please note that call_docval_func "
    "removes all arguments not accepted by the function's docval, so if you are passing kwargs that "
    "includes extra arguments and the function's docval does not allow extra arguments (allow_extra=True "
    "is set), then you will need to pop the extra arguments out of kwargs before calling the function."
)

_deprecation_warning_pandas_pyarrow_re = r"\nPyarrow will become a required dependency of pandas.*"

_deprecation_warning_datetime = r"datetime.datetime.utcfromtimestamp() *"

_deprecation_warning_zarr_store = r"The NestedDirectoryStore is deprecated *"
_deprecation_warning_numpy = (
    "__array__ implementation doesn't accept a copy keyword, so passing copy=False failed. "
    "__array__ must implement 'dtype' and 'copy' keyword arguments."
)


def run_gallery_tests():
    global TOTAL, FAILURES, ERRORS
    logging.info("Testing execution of Sphinx Gallery files")

    # get all python file names in docs/gallery
    gallery_file_names = list()
    for root, _, files in os.walk(
        os.path.join(os.path.dirname(__file__), "docs", "gallery"),
    ):
        for f in files:
            if f.endswith(".py"):
                gallery_file_names.append(os.path.join(root, f))

    warnings.simplefilter("error")

    TOTAL += len(gallery_file_names)
    curr_dir = os.getcwd()
    for script in gallery_file_names:
        logging.info("Executing %s" % script)
        os.chdir(curr_dir)  # Reset the working directory
        script_abs = os.path.abspath(script)  # Determine the full path of the script
        # Set the working dir to be relative to the script to allow the use of relative file paths in the scripts
        os.chdir(os.path.dirname(script_abs))
        try:
            with warnings.catch_warnings(record=True):
                warnings.filterwarnings("ignore", message=_deprecation_warning_map, category=DeprecationWarning)
                warnings.filterwarnings(
                    "ignore", message=_deprecation_warning_fmt_docval_args, category=PendingDeprecationWarning
                )
                warnings.filterwarnings(
                    "ignore", message=_deprecation_warning_call_docval_func, category=PendingDeprecationWarning
                )
                warnings.filterwarnings("ignore", message=_experimental_warning_re, category=UserWarning)
                warnings.filterwarnings("ignore", message=_user_warning_transpose, category=UserWarning)
                warnings.filterwarnings(
                    # this warning is triggered from pandas when HDMF is installed with the minimum requirements
                    "ignore",
                    message=_distutils_warning_re,
                    category=DeprecationWarning,
                )
                warnings.filterwarnings(
                    # this warning is triggered when some numpy extension code in an upstream package was compiled
                    # against a different version of numpy than the one installed
                    "ignore",
                    message=_numpy_warning_re,
                    category=RuntimeWarning,
                )
                warnings.filterwarnings(
                    # this warning is triggered when downstream code such as pynwb uses pkg_resources>=5.13
                    "ignore",
                    message=_pkg_resources_warning_re,
                    category=DeprecationWarning,
                )
                warnings.filterwarnings(
                    # this warning is triggered when downstream code such as pynwb uses pkg_resources>=5.13
                    "ignore",
                    message=_pkg_resources_declare_warning_re,
                    category=DeprecationWarning,
                )
                warnings.filterwarnings(
                    # this warning is triggered from pandas
                    "ignore",
                    message=_deprecation_warning_pandas_pyarrow_re,
                    category=DeprecationWarning,
                )
                warnings.filterwarnings(
                    # this is triggered from datetime
                    "ignore",
                    message=_deprecation_warning_datetime,
                    category=DeprecationWarning,
                )
                warnings.filterwarnings("ignore", message=_deprecation_warning_zarr_store, category=FutureWarning)
                warnings.filterwarnings("ignore", message=_deprecation_warning_numpy, category=DeprecationWarning)
                _import_from_file(script_abs)
        except Exception:
            print(traceback.format_exc())
            FAILURES += 1
            ERRORS += 1
    # Make sure to reset the working directory at the end
    os.chdir(curr_dir)


def main():
    logging_format = (
        "======================================================================\n"
        "%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.basicConfig(format=logging_format, level=logging.INFO)

    run_gallery_tests()

    final_message = "Ran %s tests" % TOTAL
    exitcode = 0
    if ERRORS > 0 or FAILURES > 0:
        exitcode = 1
        _list = list()
        if ERRORS > 0:
            _list.append("errors=%d" % ERRORS)
        if FAILURES > 0:
            _list.append("failures=%d" % FAILURES)
        final_message = "%s - FAILED (%s)" % (final_message, ",".join(_list))
    else:
        final_message = "%s - OK" % final_message

    logging.info(final_message)

    return exitcode


if __name__ == "__main__":
    sys.exit(main())
