# -*- python -*-

import os

# There are two aspects to using Qt in a module: the module needs to run
# moc and uic on its sources files so it needs the full support of the qt
# tool, or a module just depends upon the Qt library, possibly indirectly
# through one of its dependencies.  For the latter, the library and include
# paths need to be set in the environment so that things work even if the
# environment was not created with the qt tool.  For that matter, even if
# it was, then this is still necessary.  For example, requiring Qwt in turn
# requires Qt, and so this function makes sure the Qt library appears after
# Qwt, even if the qt tool has already added the Qt library up front.
#
# For Qt5, the only module that is enabled by default is QtCore.  Other
# Qt5 modules need to be explicitly enabled after this package is loaded.  
# That's done with the EnableQt5Modules() method, like this:
#    env.EnableQt5Modules(['QtGui', 'QtNetwork'])

def qt(env, minversion=None, maxversion=None):
  # Qt3:
  # For reasons I haven't figured out, the HOME environment variable
  # does not propagate to the environment 'uic' runs under, but
  # without it uic reports errors like
  #    QSettings::sync: cannot open /.qt
  # so this sets the HOME setting explicitly in the QT_UIC command.
  #
  if not env.has_key('HAS_PKG_QT'):
    env['HAS_PKG_QT'] = 1
    
    if minversion == None: minversion = "3"
    if maxversion == None: maxversion = "3"

    minmajor = parseMajorVersion(minversion)
    maxmajor = parseMajorVersion(maxversion)
    if maxmajor < minmajor:
      msg = "maximum version (%d) < minimum version (%d)" % (maxmajor,
                                                             minmajor)
      raise "Version error", msg

    if minmajor >= 4:
      #
      # Load the qt5 tool if we haven't yet done so
      #
      if not('qt5' in env['TOOLS']):
        #
        # Add 'qt5' to the list of tools
        #
        env.Tool('qt5')
        #
        # Enable QtCore by default
        #
        env.EnableQt5Modules(['QtCore'])
    else:
      qt3(env)

def qt3(env):
    # Look for the QTDIR setting as a construction variable, and if not
    # there expect it to come from the environment.
    try:
      qt_root = env['QTDIR']
    except KeyError:
      qt_root = os.environ['QTDIR']
      env['QTDIR'] = qt_root
    # The Qt library usually needs HOME to be set so it can access
    # the ~/.qt directory, so just add it here for the sake of any
    # test programs and Qt tools that will be run by this scons
    # environment.  If HOME does not exist, as on Windows, then don't
    # bother.
    env['ENV']['QTDIR'] = qt_root
    uic = os.path.join(qt_root,'bin','uic')
    if os.environ.has_key('HOME'):
        env['ENV']['HOME'] = os.environ['HOME']
        uic = 'HOME="%s" %s' % (os.environ['HOME'],
                                os.path.join(qt_root,'bin','uic'))
    qtlib=os.path.join(qt_root,'lib')
    env.Replace(QT_UIC = uic)
    env.Replace(QT_LIB = 'qt-mt')
#    env.AppendUnique(DEPLOY_SHARED_LIBS = ['$QT_LIB'])
    env.AppendUnique(CPPDEFINES = ['QT_THREAD_SUPPORT','_REENTRANT'])
    if env['PLATFORM'] == 'win32':
        # qmake on Windows defines WIN32, so we do too for all the qt
        # code which may depend on it.  Note that Windows compiler normally
        # only predefines _WIN32 and not WIN32.
        env.Append(CPPDEFINES=['WIN32'])

    env.AppendUnique(CPPPATH = [ os.path.join (qt_root, 'include') ] )
    env.AppendUnique(LIBPATH = [qtlib, '/usr/X11R6/lib',])
    # force the dynamic linker to find our libs
    # w/o setting LD_LIBRARY_PATH
    env.AppendUnique(RPATH=[qtlib])
    # need LD_LIBRARY_PATH set for uic to run, because SCons
    # doesn't use user's LD_LIBRARY_PATH
    env.AppendENVPath ('LD_LIBRARY_PATH',qtlib)
    env.Append(LIBS = [ env['QT_LIB'] ])
    if not env.has_key('QT_DOXDIR'):
      env['QT_DOXDIR'] = os.path.join(qt_root,'doc','html')
    if not env.has_key('QT_DOXREF'):
      env['QT_DOXREF'] = 'qt:%s' % env['QT_DOXDIR']
    env.AppendDoxref (env['QT_DOXREF'])

#
# Parse the Qt major version number from a version string
#
def parseMajorVersion(versionstring):
  try:
    return int(versionstring.split('.')[0])
  except:
    return int(versionstring)


def generate(env):
  import SCons.Tool.qt
  SCons.Tool.qt.generate(env)
  qt(env)


def exists(env):
  return True
