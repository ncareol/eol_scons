e
import os
from SCons.Variables import PathVariable
import platform
import eol_scons.parseconfig as pc

_options = None
myKey = 'HAS_PACKAGE_QWT'
USE_PKG_CONFIG = 'Using pkg-config'

def is_64bit():
    """ is this a 64-bit system? """
    return platform.machine()[-2:] == '64'

if is_64bit():
    lib_= 'lib64'
else:
    lib_= 'lib'

class QwtTool:

    def __init__(self):
        self.settings = {}

    def require(self, env):
        if not self.settings:
            import new
            env.EnableQwt = new.instancemethod(enable_qwt, env, type(env))
            self.calculate_settings(env)
        self.apply_settings(env)

    def calculate_settings(self, env):
        qwt_dir = find_qwtdir(env)
        if not qwt_dir:
            return

        self.settings['QWTDIR'] = qwt_dir
        qwt_libdir = os.path.join(qwt_dir, lib_)
        libqwt = os.path.join(qwt_libdir, 'libqwt.so')

        # These settings apply whether located manually or with pkg-config
        qwt_docdir = os.path.join(qwt_dir, 'doc', 'html')
        self.settings['QWT_DOXREF'] = 'qwt:' + qwt_docdir

        if (qwt_dir == USE_PKG_CONFIG):
            return
            
        if env['PLATFORM'] != 'darwin':
            self.settings['LIBS'] = ['qwt']
            self.settings['LIBPATH'] = [qwt_libdir]
        else:
            self.settings['FRAMEWORKPATH'] = '/usr/local/lib'
            self.settings['FRAMEWORKS']    = 'qwt'

        self.settings['RPATH'] = [qwt_libdir]
        if env['PLATFORM'] != 'darwin':
            if qwt_dir != "/usr":
                self.settings['CPPPATH'] = [os.path.join(qwt_dir, 'include')]
            else:
                self.settings['CPPPATH'] = [os.path.join(qwt_dir, 'include','qwt')]
        else:
                self.settings['CPPPATH'] = '/usr/local/lib/qwt.framework/Headers'
        plugindir='$QWTDIR/designer/plugins/designer'
        self.settings['QT_UICIMPLFLAGS'] = ['-L', plugindir]
        self.settings['QT_UICDECLFLAGS'] = ['-L', plugindir]


    def apply_settings(self, env):

        try:
            env['QWTDIR'] = self.settings['QWTDIR']
        except KeyError:
            return

        if not env.has_key('QWT_DOXREF'):
            env['QWT_DOXREF'] = self.settings['QWT_DOXREF']
        env.AppendDoxref(env['QWT_DOXREF'])

        if (self.settings['QWTDIR'] == USE_PKG_CONFIG):
            # Don't try here to make things unique in CFLAGS; just do an append
            env.ParseConfig('pkg-config --cflags ' + self.pkgConfigName, unique = False)
            env.ParseConfig('pkg-config --libs ' + self.pkgConfigName, unique = False)
            return

        if env['PLATFORM'] != 'darwin':
            env.Append(LIBS=self.settings['LIBS'])
            env.AppendUnique(LIBPATH=self.settings['LIBPATH'])
        else:
            env.AppendUnique(FRAMEWORKPATH=self.settings['FRAMEWORKPATH'])
            env.AppendUnique(FRAMEWORKS=self.settings['FRAMEWORKS'])

        env.AppendUnique(RPATH=self.settings['RPATH'])
        env.Append(CPPPATH=self.settings['CPPPATH'])
        env.Append(QT_UICIMPLFLAGS=self.settings['QT_UICIMPLFLAGS'])
        env.Append(QT_UICDECLFLAGS=self.settings['QT_UICDECLFLAGS'])

    def findPkgConfig(self, env):
        """
        See if pkg-config knows about Qwt on this system.

        This gets the pkg-config results specific to this Environment, to
        account for settings like PKG_CONFIG_PATH. However, only one
        instance of QwtTool is ever created by this tool, on the assumption
        that the qwt settings would be the same for all environments.  So
        this may break for cross-builds or situations where different
        Environments need to use a different PKG_CONFIG_PATH.
        """
        for qname in ['qwt', 'Qwt']:
            try:
                if pc.CheckConfig(env, 'pkg-config ' + qname):
                    self.pkgConfigName = qname
                    return True
            except:
                return False
        return False

def enable_qwt(env):
    # This configure test for qwt must be delayed, and not done
    # by the generate() function when this qwt tool is loaded.
    # This is because the qt5 build environment is not fully setup
    # when qt5 tool is loaded via its generate() function. The
    # user must call env.EnableQt5Modules(['QtCore',...]) after the
    # qt5 tool is loaded to setup the Qt build environment.
    # Then call env.EnableQwt(), and this Configure check has
    # a chance of succeeding.

    if False:
        # When doing a CheckLibWithHeader one must clean out LIBS
        # so that it doesn't contain any target libraries that are built
        # by this run of scons. Otherwise those libraries will be built
        # as part of the check, which leads to major confusion.
        # We need the Qt libraries, however.
        qtlibs = [ lib for lib in env['LIBS'] if str(lib).startswith('Qt') ]
        conf = env.Clone(LIBS=qtlibs).Configure(clean=False, help=False)
        hasQwt = conf.CheckLibWithHeader('qwt','qwt.h','c++',autoadd=False)
        conf.Finish()

    hasQwt = True
    skipconfig = env.GetOption('help') or env.GetOption('clean')
    if not skipconfig:
        # Do a simple CheckCXXHeader('qwt.h') instead of the more complete
        # CheckLibWithHeader(...), above.
        conf = env.Configure()
        hasQwt = conf.CheckCXXHeader('qwt.h')
        conf.Finish()
    return hasQwt

qwt_tool = QwtTool()

def find_qwtdir(env):
    qwtdir = None

    pkgConfigKnowsQwt = qwt_tool.findPkgConfig(env)

    # 
    # Try to find the Qwt installation location, trying in order:
    #    o command line QWTDIR option (or otherwise set in the environment)
    #    o OS environment QWTDIR
    #    o installation defined via pkg-config (this is the preferred method)
    #    o lastly see if lib_/libqwt.so exists under OPT_PREFIX
    #
    if (env.has_key('QWTDIR')):
        qwtdir = env['QWTDIR']
    elif (os.environ.has_key('QWTDIR')):
        qwtdir = os.environ['QWTDIR']
    elif pkgConfigKnowsQwt:
        qwtdir = USE_PKG_CONFIG
    elif (env.has_key('OPT_PREFIX') and 
          os.path.exists(os.path.join(env['OPT_PREFIX'], lib_, 'libqwt.so'))):
        qwtdir = env['OPT_PREFIX']
    else:
        qwtdir = "/usr"
    print("qwtdir set to '%s'" % (qwtdir))
    return qwtdir


def generate(env):
    global _options
    if not _options:
        _options = env.GlobalVariables()
        _options.AddVariables(PathVariable('QWTDIR', 'Qwt installation root.', 
                                           None))
    _options.Update(env)

    #
    # One-time stuff if this tool hasn't been loaded yet
    #
    if (not env.has_key(myKey)):
        #
        # We should also require Qt here, but which version?
        #
        #env.Require(['qt', 'doxygen'])
	env.Require(['doxygen'])
        
    qwt_tool.require(env)
    env[myKey] = True


def exists(env):
    return True

