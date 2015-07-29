# -*- mode: python -*-
import os
import sys
from os.path import join, exists, realpath, abspath
import utool as ut
# import utool

# Pyinstaller Variables (enumerated for readability, not needed)
#Analysis = Analysis  # NOQA


def join_SITE_PACKAGES(*args):
    def get_site_package_directories():
        import site
        import sys
        import six
        sitepackages = site.getsitepackages()
        if sys.platform.startswith('darwin'):
            if six.PY2:
                macports_site = '/opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages'
            else:
                macports_site = '/opt/local/Library/Frameworks/Python.framework/Versions/3.5/lib/python3.5/site-packages'
                assert six.PY2, 'fix this for python 3'
            sitepackages = [macports_site] + sitepackages
        return sitepackages
    from os.path import join
    import utool as ut
    fname = join(*args)
    sitepackages = get_site_package_directories()
    path, tried_list = ut.search_in_dirs(fname, sitepackages, return_tried=True, strict=True)
    return path


def add_data(a, dst, src):
    global LIB_EXT
    from os.path import dirname, exists
    import utool as ut
    if dst == '':
        raise ValueError('dst path cannot be the empty string')
    if src == '':
        raise ValueError('src path cannot be the empty string')
    src_ = ut.platform_path(src)
    if not os.path.exists(dirname(dst)) and dirname(dst) != "":
        os.makedirs(dirname(dst))
    _pretty_path = lambda str_: str_.replace('\\', '/')
    # Default datatype is DATA
    dtype = 'DATA'
    # Infer datatype from extension
    #extension = splitext(dst)[1].lower()
    #if extension == LIB_EXT.lower():
    if LIB_EXT[1:] in dst.split('.'):
        dtype = 'BINARY'
    print(ut.codeblock('''
    [installer] a.add_data(
    [installer]    dst=%r,
    [installer]    src=%r,
    [installer]    dtype=%s)''') %
          (_pretty_path(dst), _pretty_path(src_), dtype))
    assert exists(src_), 'src_=%r does not exist'
    a.datas.append((dst, src_, dtype))


# Build data before running analysis for quick debugging
DATATUP_LIST = []
BINARYTUP_LIST = []

##################################
# System Variables
##################################
PLATFORM = sys.platform
APPLE = PLATFORM.startswith('darwin')
WIN32 = PLATFORM.startswith('win32')
LINUX = PLATFORM.startswith('linux2')

LIB_EXT = {'win32': '.dll',
           'darwin': '.dylib',
           'linux2': '.so'}[PLATFORM]

##################################
# Asserts
##################################
ibsbuild = ''
root_dir = os.getcwd()
try:
    assert exists(join(root_dir, 'installers.py'))
    assert exists('../ibeis')
    assert exists('../ibeis/ibeis')
    assert exists(root_dir)
except AssertionError:
    raise Exception('installers.py must be run from ibeis root')

##################################
# Explicitly add modules in case they are not in the Python PATH
##################################
module_repos = [
    'utool',
    'vtool',
    'guitool',
    'guitool.__PYQT__',
    'plottool',
    'pyrf',
    'flann/src/python',
    #'pygist',
    'ibeis',
    'hesaff',
    'detecttools'
]
pathex = ['.'] + [ join('..', repo) for repo in module_repos ]
if APPLE:
    # We need to explicitly add the MacPorts and system Python site-packages folders on Mac
    pathex.append('/opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/site-packages/')
    pathex.append('/System/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/')

# IF MPL FAILS:
# MPL has a problem where the __init__.py is not created in the library.  touch __init__.py in the module's path should fix the issue

##################################
# Hesaff + PyRF + FLANN Library
##################################

#import pyhesaff
#pyhesaff.HESAFF_CLIB.__LIB_FPATH__
#import pyrf
#pyrf.RF_CLIB.__LIB_FPATH__
# Hesaff
libhesaff_fname = 'libhesaff' + LIB_EXT
libhesaff_src = realpath(join(root_dir, '..', 'hesaff', 'pyhesaff', libhesaff_fname))
libhesaff_dst = join(ibsbuild, 'pyhesaff', 'lib', libhesaff_fname)
DATATUP_LIST.append((libhesaff_dst, libhesaff_src))

# PyRF
libpyrf_fname = 'libpyrf' + LIB_EXT
libpyrf_src = realpath(join(root_dir, '..', 'pyrf', 'pyrf', libpyrf_fname))
libpyrf_dst = join(ibsbuild, 'pyrf', 'lib', libpyrf_fname)
DATATUP_LIST.append((libpyrf_dst, libpyrf_src))


# FLANN
libflann_fname = 'libflann' + LIB_EXT
#try:
#    #import pyflann
#    #pyflann.__file__
#    #join(dirname(dirname(pyflann.__file__)), 'build')
#except ImportError as ex:
#    print('PYFLANN IS NOT IMPORTABLE')
#    raise
#if WIN32 or LINUX:
# FLANN
#libflann_src = join_SITE_PACKAGES('pyflann', 'lib', libflann_fname)
#libflann_dst = join(ibsbuild, libflann_fname)
#elif APPLE:
#    # libflann_src = '/pyflann/lib/libflann.dylib'
#    # libflann_dst = join(ibsbuild, libflann_fname)
#    libflann_src = join_SITE_PACKAGES('pyflann', 'lib', libflann_fname)
#    libflann_dst = join(ibsbuild, libflann_fname)
# This path is when pyflann was built using setup.py develop
libflann_src = realpath(join(root_dir, '..', 'flann', 'build', 'lib', libflann_fname))
libflann_dst = join(ibsbuild, 'pyflann', 'lib', libflann_fname)
DATATUP_LIST.append((libflann_dst, libflann_src))


linux_lib_dpaths = [
    '/usr/lib/x86_64-linux-gnu',
    '/usr/lib',
    '/usr/local/lib'
]

# OpenMP
if APPLE:
    # BSDDB, Fix for the modules that PyInstaller needs and (for some reason)
    # are not being added by PyInstaller
    libbsddb_src = '/opt/local/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/lib-dynload/_bsddb.so'
    libbsddb_dst = join(ibsbuild, '_bsddb.so')
    DATATUP_LIST.append((libbsddb_dst, libbsddb_src))
    #libgomp_src = '/opt/local/lib/libgomp.dylib'
    libgomp_src = '/opt/local/lib/gcc48/libgomp.dylib'
    BINARYTUP_LIST.append(('libgomp.1.dylib', libgomp_src, 'BINARY'))
    libgomp_src = '/Users/bluemellophone/code/libomp_oss/exports/mac_32e/lib.thin/libiomp5.dylib'
    BINARYTUP_LIST.append(('libiomp5.dylib', libgomp_src, 'BINARY'))
if LINUX:
    libgomp_src = ut.search_in_dirs('libgomp.so.1', linux_lib_dpaths)
    #libgomp_src = join('/usr', 'lib',  'libgomp.so.1')
    #assert ut.checkpath(libgomp_src):
    ut.assertpath(libgomp_src)
    #libgomp_src = join('/usr', 'lib',  'libgomp.so.1')
    # ut.assertpath(libgomp_src)
    BINARYTUP_LIST.append(('libgomp.so.1', libgomp_src, 'BINARY'))


# MinGW
if WIN32:
    mingw_root = r'C:\MinGW\bin'
    mingw_dlls = ['libgcc_s_dw2-1.dll', 'libstdc++-6.dll', 'libgomp-1.dll', 'pthreadGC2.dll']
    for lib_fname in mingw_dlls:
        lib_src = join(mingw_root, lib_fname)
        lib_dst = join(ibsbuild, lib_fname)
        DATATUP_LIST.append((lib_dst, lib_src))

# We need to add these 4 opencv libraries because pyinstaller does not find them.
#OPENCV_EXT = {'win32': '248.dll',
#              'darwin': '.2.4.dylib',
#              'linux2': '.so.2.4'}[PLATFORM]

target_cv_version = '3.0.0'

OPENCV_EXT = {'win32': target_cv_version.replace('.', '') + '.dll',
              'darwin': '.' + target_cv_version + '.dylib',
              'linux2': '.so.' + target_cv_version}[PLATFORM]

missing_cv_name_list = [
    'libopencv_videostab',
    'libopencv_superres',
    'libopencv_stitching',
    #'libopencv_gpu',
    'libopencv_core',
    'libopencv_highgui',
    'libopencv_imgproc',
]
# Hack to find the appropriate opencv libs
for name in missing_cv_name_list:
    fname = name + OPENCV_EXT
    src = ''
    dst = ''
    if APPLE:
        src = join('/opt/local/lib', fname)
    elif LINUX:
        #src = join('/usr/lib', fname)
        src, tried = ut.search_in_dirs(fname, linux_lib_dpaths, strict=True, return_tried=True)
    elif WIN32:
        import utool as ut
        if ut.get_computer_name() == 'Ooo':
            src = join(r'C:/Program Files (x86)/OpenCV/x86/mingw/bin', fname)
        else:
            src = join(root_dir, '../opencv/build/bin', fname)
    dst = join(ibsbuild, fname)
    # ut.assertpath(src)
    DATATUP_LIST.append((dst, src))


##################################
# QT Gui dependencies
##################################
if APPLE:
    walk_path = '/opt/local/Library/Frameworks/QtGui.framework/Versions/4/Resources/qt_menu.nib'
    for root, dirs, files in os.walk(walk_path):
        for lib_fname in files:
            toc_src = join(walk_path, lib_fname)
            toc_dst = join('qt_menu.nib', lib_fname)
            DATATUP_LIST.append((toc_dst, toc_src))

##################################
# Documentation, Icons, and Web Assets
##################################
# Documentation
#userguide_dst = join('.', '_docs', 'IBEISUserGuide.pdf')
#userguide_src = join(root_dir, '_docs', 'IBEISUserGuide.pdf')
#DATATUP_LIST.append((userguide_dst, userguide_src))

# Icon File
ICON_EXT = {'darwin': '.icns',
            'win32':  '.ico',
            'linux2': '.ico'}[PLATFORM]
iconfile = join('_installers', 'ibsicon' + ICON_EXT)
icon_src = join(root_dir, iconfile)
icon_dst = join(ibsbuild, iconfile)
DATATUP_LIST.append((icon_dst, icon_src))

# Web Assets
INSTALL_WEB = True
if INSTALL_WEB:
    web_root = join('ibeis', 'web/')
    walk_path = join(web_root, 'static')
    for root, dirs, files in os.walk(walk_path):
        root2 = root.replace(web_root, '')
        for icon_fname in files:
            if '.DS_Store' not in icon_fname:
                toc_src = join(abspath(root), icon_fname)
                toc_dst = join(root2, icon_fname)
                DATATUP_LIST.append((toc_dst, toc_src))

    web_root = join('ibeis', 'web/')
    walk_path = join(web_root, 'templates')
    for root, dirs, files in os.walk(walk_path):
        root2 = root.replace(web_root, '')
        for icon_fname in files:
            if '.DS_Store' not in icon_fname:
                toc_src = join(abspath(root), icon_fname)
                toc_dst = join(root2, icon_fname)
                DATATUP_LIST.append((toc_dst, toc_src))

##################################
# Build executable
##################################
# Executable name
exe_name = {'win32':  'build/IBEISApp.exe',
            'darwin': 'build/pyi.darwin/IBEISApp/IBEISApp',
            'linux2': 'build/IBEISApp'}[PLATFORM]

print('[installer] Checking Data')
try:
    for (dst, src) in DATATUP_LIST:
        assert ut.checkpath(src, verbose=True), 'checkpath for src=%r failed' % (src,)
except Exception as ex:
    ut.printex(ex, 'Checking data failed DATATUP_LIST=%s' + ut.list_str(DATATUP_LIST))
    raise
# print('[installer] Checking Data')
# for (dst, src) in DATATUP_LIST:
#     assert ut.checkpath(src, verbose=True), 'checkpath failed'

#import sys
#print('exiting')
#sys.exit(1)

print('[installer] Running Analysis')
a = Analysis(  # NOQA
    #['main.py'],
    ['ibeis/__main__.py'],
    pathex=pathex,
    hiddenimports=[
        'guitool.__PYQT__',
        'sklearn.utils.sparsetools._graph_validation',
        'sklearn.utils.sparsetools._graph_tools',
        'scipy.special._ufuncs_cxx',
        'sklearn.utils.lgamma',
        'sklearn.utils.weight_vector',
        'sklearn.neighbors.typedefs',
        'mpl_toolkits.axes_grid1',
    ],
    hookspath=None,
    runtime_hooks=[
        '_installers/rthook_pyqt4.py'
    ]
)

print('[installer] Adding %d Datatups' % (len(DATATUP_LIST,)))
for (dst, src) in DATATUP_LIST:
    add_data(a, dst, src)

print('[installer] Adding %d Binaries' % (len(BINARYTUP_LIST),))
for binarytup in BINARYTUP_LIST:
    a.binaries.append(binarytup)

print('[installer] PYZ Step')
pyz = PYZ(a.pure)   # NOQA

exe_kwargs = {
    'console': True,
    'debug': False,
    'name': exe_name,
    'exclude_binaries': True,
    'append_pkg': False,
}

collect_kwargs = {
    'strip': None,
    'upx': True,
    'name': join('dist', 'ibeis')
}

# Windows only EXE options
if WIN32:
    exe_kwargs['icon'] = join(root_dir, iconfile)
    #exe_kwargs['version'] = 1.5
if APPLE:
    exe_kwargs['console'] = False

# Pyinstaller will gather .pyos
print('[installer] EXE Step')
opt_flags = [('O', '', 'OPTION')]
exe = EXE(pyz, a.scripts + opt_flags, **exe_kwargs)   # NOQA

print('[installer] COLLECT Step')
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, **collect_kwargs)  # NOQA

bundle_name = 'IBEIS'
if APPLE:
    bundle_name += '.app'

print('[installer] BUNDLE Step')
app = BUNDLE(coll, name=join('dist', bundle_name))  # NOQA
