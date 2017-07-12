# -*- python -*-

"""
This tool adds Qt5 include paths and libraries to the build
environment.  Since Qt5 is divided into many different modules, the modules
can be applied to the environment individually using either the
EnableQt5Modules() method or by listing the module as a tool.  For example,
these are equivalent:

    qtmods = ['QtSvg', 'QtCore', 'QtGui', 'QtNetwork', 'QtSql', 'QtOpenGL']
    env.EnableQt5Modules(qtmods)

    env.Require(Split("qtsvg qtcore qtgui qtnetwork qtsql qtopengl"))

If a Qt5 module is optional, such as disabling the build of a Qt GUI
application when the QtGui module is not present, then the
return value from the EnableQt5Modules() method must be used:

    qt5Modules = Split('QtGui QtCore QtNetwork')
    if not env.EnableQt5Modules(qt5Modules):
        Return()
"""

import re
import os

import SCons.Defaults
import SCons.Node
import SCons.Tool
import SCons.Util
from SCons.Variables import PathVariable
from SCons.Script import Scanner

import eol_scons.parseconfig as pc
import eol_scons
from eol_scons import Debug

_options = None
USE_PKG_CONFIG = "Using pkg-config"
myKey = "HAS_TOOL_QT5"

class ToolQt5Warning(SCons.Warnings.Warning):
    pass
class GeneratedMocFileNotIncluded(ToolQt5Warning):
    pass
class Qt5ModuleIssue(ToolQt5Warning):
    pass
SCons.Warnings.enableWarningClass(ToolQt5Warning)

qrcinclude_re = re.compile(r'<file[^>]*>([^<]*)</file>', re.M)


header_extensions = [".h", ".hxx", ".hpp", ".hh"]
if SCons.Util.case_sensitive_suffixes('.h', '.H'):
    header_extensions.append('.H')
cxx_suffixes = [".c", ".cxx", ".cpp", ".cc"]

def _checkMocIncluded(target, source, env):
    moc = target[0]
    cpp = source[0]
    # looks like cpp.includes is cleared before the build stage :-(
    # not really sure about the path transformations (moc.cwd? cpp.cwd?) :-/
    path = SCons.Defaults.CScan.path_function(env, moc.cwd)
    includes = SCons.Defaults.CScan(cpp, env, path)
    if not moc in includes:
        SCons.Warnings.warn(
            GeneratedMocFileNotIncluded,
            "Generated moc file '%s' is not included by '%s'" %
            (str(moc), str(cpp)))

def _find_file(filename, paths, node_factory):
    retval = None
    for dir in paths:
        node = node_factory(filename, dir)
        if node.rexists():
            return node
    return None

class _Automoc:
    """
    Callable class, which works as an emitter for Programs, SharedLibraries and
    StaticLibraries.
    """

    def __init__(self, objBuilderName):
        self.objBuilderName = objBuilderName

    def __call__(self, target, source, env):
        """
        Smart autoscan function. Gets the list of objects for the Program
        or Lib. Adds objects and builders for the special qt5 files.
        """
        try:
            if int(env.subst('$QT_AUTOSCAN')) == 0:
                return target, source
        except ValueError:
            pass
        try:
            debug = int(env.subst('$QT_DEBUG'))
        except ValueError:
            debug = 0
        if debug and not eol_scons.debug:
            eol_scons.SetDebug(True)

        # some shortcuts used in the scanner
        FS = SCons.Node.FS.default_fs
        objBuilder = getattr(env, self.objBuilderName)

        # some regular expressions:
        # Q_OBJECT detection
        q_object_search = re.compile(r'[^A-Za-z0-9]Q_OBJECT[^A-Za-z0-9]') 
        # cxx and c comment 'eater'
        #comment = re.compile(r'(//.*)|(/\*(([^*])|(\*[^/]))*\*/)')
        # CW: something must be wrong with the regexp. See also bug #998222
        #     CURRENTLY THERE IS NO TEST CASE FOR THAT

        # The following is kind of hacky to get builders working properly (FIXME)
        objBuilderEnv = objBuilder.env
        objBuilder.env = env
        mocBuilderEnv = env.Moc5.env
        env.Moc5.env = env

        # make a deep copy for the result; MocH objects will be appended
        out_sources = source[:]

        Debug("%s: scanning [%s] to add targets to [%s]." %
              (self.objBuilderName, 
               ",".join([str(s) for s in source]),
               ",".join([str(t) for t in target])), env)
        for obj in source:
            #
            # KLUGE: If the obj is not a SCons.Node.FS.Entry, it may be a list
            # containing only the entry.  If we get a list of length one, just
            # use its single entry as the obj.  Not sure why this has become
            # an issue now...
            #
            if (not isinstance(obj, SCons.Node.FS.Entry)):
                try:
                    if (len(obj) != 1):
                        raise Error
                    obj = obj[0]
                except:
                    errmsg = "qt5/_Automoc_ got a bad source object: "
                    errmsg += str(obj)
                    raise SCons.Errors.StopError, errmsg                    

            if not obj.has_builder():
                # binary obj file provided
                Debug("scons: qt5: '%s' seems to be a binary. Discarded." % 
                      str(obj), env)
                continue

            cpp = obj.sources[0]
            if not SCons.Util.splitext(str(cpp))[1] in cxx_suffixes:
                Debug("scons: qt5: '%s' is not a C++ file. Discarded." % 
                      str(cpp), env)
                # c or fortran source
                continue
            #cpp_contents = comment.sub('', cpp.get_contents())
            cpp_contents = cpp.get_contents()
            h=None
            for h_ext in header_extensions:
                # try to find the header file in the corresponding source
                # directory
                hname = SCons.Util.splitext(cpp.name)[0] + h_ext
                h = _find_file(hname,
                              (cpp.get_dir(),),
                              FS.File)
                if h:
                    Debug("scons: qt5: Scanning '%s' (header of '%s')" % 
                          (str(h), str(cpp)), env)
                    #h_contents = comment.sub('', h.get_contents())
                    h_contents = h.get_contents()
                    break
            if not h:
                Debug("scons: qt5: no header for '%s'." % (str(cpp)), env)
            if h and q_object_search.search(h_contents):
                # h file with the Q_OBJECT macro found -> add moc_cpp
                moc_cpp = env.Moc5(h)
                moc_o = objBuilder(moc_cpp)
                out_sources.append(moc_o)
                #moc_cpp.target_scanner = SCons.Defaults.CScan
                Debug("scons: qt5: found Q_OBJECT macro in '%s', "
                      "moc'ing to '%s'" % (str(h), str(moc_cpp)), env)
            if cpp and q_object_search.search(cpp_contents):
                # cpp file with Q_OBJECT macro found -> add moc
                # (to be included in cpp)
                moc = env.Moc5(cpp)
                env.Ignore(moc, moc)
                Debug("scons: qt5: found Q_OBJECT macro in '%s', "
                      "moc'ing to '%s'" % (str(cpp), str(moc)), env)
                #moc.source_scanner = SCons.Defaults.CScan
        # restore the original env attributes (FIXME)
        objBuilder.env = objBuilderEnv
        env.Moc5.env = mocBuilderEnv

        return (target, out_sources)

AutomocShared = _Automoc('SharedObject')
AutomocStatic = _Automoc('StaticObject')

def _locateQt5Command(env, command) :
    # Check the cache
    cache = env.CacheVariables()
    key = "qt5_" + command
    result = cache.lookup(env, key)
    if result:
        return result

    # Look for <command>-qt5, followed by just <command>
    commandQt5 = command + '-qt5'
    cmds = [commandQt5, command]

    qt5BinDir = None
    #
    # If env['QT5DIR'] is defined, add the associated bin directory to our
    # search path for the commands
    #
    if (env.has_key('QT5DIR')):
        # If we're using pkg-config, assume all Qt5 binaries live in 
        # <prefix_from_pkgconfig>/bin.  This is slightly dangerous,
        # but seems to match all installation schemes I've seen so far,
        # and the "prefix" variable appears to always be available (again,
        # so far...).
        if (env['QT5DIR'] == USE_PKG_CONFIG):
            qt5Prefix = pc.RunConfig(env, 'pkg-config --variable=prefix QtCore')
            qt5BinDir = os.path.join(qt5Prefix, 'bin')
        # Otherwise, look for Qt5 binaries in <QT5DIR>/bin
        else:
            qt5BinDir = os.path.join(env['QT5DIR'], 'bin')

    # If we built a qt5BinDir, check (only) there first for the command. 
    # This will make sure we get e.g., <myQT5DIR>/bin/moc ahead of 
    # /usr/bin/moc-qt5 in the case where we have a standard installation 
    # but we're trying to use a custom one by setting QT5DIR.
    if (qt5BinDir):
        # check for the binaries in *just* qt5BinDir
        result = reduce(lambda a,b: a or env.WhereIs(b, [qt5BinDir]), 
                        cmds, None)

    # Check the default path
    if not result:
        result = env.Detect(cmds)

    if not result:
        msg = "Qt5 command " + commandQt5 + " (" + command + ")"
        if (qt5BinDir):
            msg += " not in " + qt5BinDir + ","
        msg += " not in $PATH"
        raise SCons.Errors.StopError, msg

    cache.store(env, key, result)
    return result


tsbuilder = None
qmbuilder = None
qrcscanner = None
qrcbuilder = None
uic5builder = None
mocBld = None

def _scanResources(node, env, path, arg):
    contents = node.get_contents()
    includes = qrcinclude_re.findall(contents)
    return includes


def create_builders():
    global tsbuilder, qmbuilder, qrcscanner, qrcbuilder, uic5builder, mocBld

    # Translation builder
    tsbuilder = SCons.Builder.Builder(action =
                                      '$QT5_LUPDATE $SOURCES -ts $TARGETS',
                                      multi=1)
    qmbuilder = SCons.Builder.Builder(action =['$QT5_LRELEASE $SOURCE',    ],
                                      src_suffix = '.ts',
                                      suffix = '.qm',
                                      single_source = True)

    # Resource builder
    qrcscanner = Scanner(name = 'qrcfile',
        function = _scanResources,
        argument = None,
        skeys = ['.qrc'])
    qrcbuilder = SCons.Builder.Builder(
        action='$QT5_RCC $QT5_QRCFLAGS $SOURCE -o $TARGET',
        source_scanner = qrcscanner,
        src_suffix = '$QT5_QRCSUFFIX',
        suffix = '$QT5_QRCCXXSUFFIX',
        prefix = '$QT5_QRCCXXPREFIX',
        single_source = True)
    uic5builder = SCons.Builder.Builder(action='$QT5_UIC5CMD',
                                        src_suffix='$QT5_UISUFFIX',
                                        suffix='$QT5_UICDECLSUFFIX',
                                        prefix='$QT5_UICDECLPREFIX',
                                        single_source = True)
    mocBld = SCons.Builder.Builder(action={}, prefix={}, suffix={})
    for h in header_extensions:
        mocBld.add_action(h, '$QT5_MOCFROMHCMD')
        mocBld.prefix[h] = '$QT5_MOCHPREFIX'
        mocBld.suffix[h] = '$QT5_MOCHSUFFIX'
    for cxx in cxx_suffixes:
        mocBld.add_action(cxx, '$QT5_MOCFROMCXXCMD')
        mocBld.prefix[cxx] = '$QT5_MOCCXXPREFIX'
        mocBld.suffix[cxx] = '$QT5_MOCCXXSUFFIX'


create_builders()


_pkgConfigKnowsQt5 = None

def checkPkgConfig(env):
    #
    # See if pkg-config knows about Qt5 on this system
    #
    global _pkgConfigKnowsQt5
    if _pkgConfigKnowsQt5 == None:
        check = pc.CheckConfig(env, 'pkg-config --exists QtCore')
        _pkgConfigKnowsQt5 = check
    return _pkgConfigKnowsQt5


def generate(env):
    """Add Builders and construction variables for qt5 to an Environment."""

    # Only need to setup any particular environment once.
    if env.has_key(myKey):
        return

    global _options
    if not _options:
        _options = env.GlobalVariables()
        _options.AddVariables(PathVariable('QT5DIR',
       'Parent directory of qt5 bin, include and lib sub-directories. The default location is determined from the path to qt5 tools and from pkg-config, so QT5DIR typically does not need to be specified.', None, PathVariable.PathAccept))
    _options.Update(env)

    # 
    # Try to find the Qt5 installation location, trying in order:
    #    o command line QT5DIR option
    #    o OS environment QT5DIR
    #    o installation defined via pkg-config (this is the preferred method)
    #    o parent of directory holding moc-qt5 in the execution path
    #    o parent of directory holding moc in the execution path
    # At the end of checking, either env['QT5DIR'] will point to the
    # top of the installation, it will be set to USE_PKG_CONFIG, or 
    # we will raise an exception.
    #
    if (env.has_key('QT5DIR')):
        pass
    elif (os.environ.has_key('QT5DIR')):
        env['QT5DIR'] = os.environ['QT5DIR']
    elif (env['PLATFORM'] == 'win32'):
        print
        print "For Windows, QT5DIR must be set" + \
            " on the command line or in the environment."
        print "E.g.:"
        print "    scons QT5DIR='/c/QtSDK/Desktop/Qt/4.7.4/mingw'"
        print
    elif checkPkgConfig(env):
        env['QT5DIR'] = USE_PKG_CONFIG
    else:
        moc = env.WhereIs('moc-qt5') or env.WhereIs('moc')
        if moc:
            env['QT5DIR'] = os.path.dirname(os.path.dirname(moc))
        elif os.path.exists('/usr/lib64/qt5'):
            env['QT5DIR'] = '/usr/lib64/qt5';
        elif os.path.exists('/usr/lib/qt5'):
            env['QT5DIR'] = '/usr/lib/qt5';

    import new
    env.EnableQt5Modules = new.instancemethod(enable_modules, env, type(env))

    if not env.has_key('QT5DIR'):
	# Dont stop, just print a warning. Later, a user call of
	# EnableQtModules() will return False if QT5DIR is not found.

        errmsg = "Qt5 not found, try setting QT5DIR."
        # raise SCons.Errors.StopError, errmsg
	print errmsg
	return

    # the basics
    env['QT5_MOC'] = _locateQt5Command(env, 'moc')
    env['QT5_UIC'] = _locateQt5Command(env, 'uic')
    env['QT5_RCC'] = _locateQt5Command(env, 'rcc')
    env['QT5_LUPDATE'] = _locateQt5Command(env, 'lupdate')
    env['QT5_LRELEASE'] = _locateQt5Command(env, 'lrelease')

    # Should the qt5 tool try to figure out which sources are to be moc'ed ?
    env['QT5_AUTOSCAN'] = 1

    # Some QT specific flags. I don't expect someone wants to
    # manipulate those ...
    env['QT5_UICDECLFLAGS'] = ''
    env['QT5_MOCFROMHFLAGS'] = ''
    env['QT5_MOCFROMCXXFLAGS'] = '-i'
    env['QT5_QRCFLAGS'] = ''

    # suffixes/prefixes for the headers / sources to generate
    env['QT5_MOCHPREFIX'] = 'moc_'
    env['QT5_MOCHSUFFIX'] = '$CXXFILESUFFIX'
    env['QT5_MOCCXXPREFIX'] = 'moc_'
    env['QT5_MOCCXXSUFFIX'] = '.moc'
    env['QT5_UISUFFIX'] = '.ui'
    env['QT5_UICDECLPREFIX'] = 'ui_'
    env['QT5_UICDECLSUFFIX'] = '.h'
    env['QT5_QRCSUFFIX'] = '.qrc',
    env['QT5_QRCCXXSUFFIX'] = '$CXXFILESUFFIX'
    env['QT5_QRCCXXPREFIX'] = 'qrc_'

    env.Append( BUILDERS = { 'Ts': tsbuilder } )
    env.Append( BUILDERS = { 'Qm': qmbuilder } )

    env.Append(SCANNERS = qrcscanner)
    env.Append( BUILDERS = { 'Qrc': qrcbuilder } )

    # Interface builder
    env['QT5_UIC5CMD'] = [
        SCons.Util.CLVar('$QT5_UIC $QT5_UICDECLFLAGS -o ${TARGETS[0]} $SOURCE'),
        ]
    env.Append( BUILDERS = { 'Uic5': uic5builder } )

    # Metaobject builder
    env['QT5_MOCFROMHCMD'] = (
        '$QT5_MOC $QT5_MOCFROMHFLAGS -o ${TARGETS[0]} $SOURCE')
    env['QT5_MOCFROMCXXCMD'] = [
        SCons.Util.CLVar('$QT5_MOC $QT5_MOCFROMCXXFLAGS -o ${TARGETS[0]} $SOURCE'),
        SCons.Action.Action(_checkMocIncluded,None)]
    env.Append( BUILDERS = { 'Moc5': mocBld } )

    # er... no idea what that was for
    static_obj, shared_obj = SCons.Tool.createObjBuilders(env)
    static_obj.src_builder.append('Uic5')
    shared_obj.src_builder.append('Uic5')
    
    # We use the emitters of Program / StaticLibrary / SharedLibrary
    # to scan for moc'able files
    # We can't refer to the builders directly, we have to fetch them
    # as Environment attributes because that sets them up to be called
    # correctly later by our emitter.
    #env.AppendUnique(PROGEMITTER =[AutomocStatic],
    #                 SHLIBEMITTER=[AutomocShared],
    #                 LIBEMITTER  =[AutomocStatic],
    #                 # Of course, we need to link against the qt5 libraries
    #                 CPPPATH=[os.path.join('$QT5DIR', 'include')],
    #                 LIBPATH=[os.path.join('$QT5DIR', 'lib')],
    env.AppendUnique(PROGEMITTER =[AutomocStatic],
                     SHLIBEMITTER=[AutomocShared],
                     LIBEMITTER  =[AutomocStatic])

    env[myKey] = True


def _checkQtCore(env):
    if env.has_key('QT5_CORE_CHECK'):
        return env['QT5_CORE_CHECK']
    conf = env.Clone(LIBS=[]).Configure()
    hasQt = conf.CheckLibWithHeader('QtCore', 'QtCore/Qt', 'c++')
    conf.Finish()
    if not hasQt:
        Debug('QtCore/Qt header file not found. '
              'Do "scons --config=force" to redo the check. '
              'See config.log for more information', env)
    env['QT5_CORE_CHECK'] = hasQt
    return hasQt


no_pkgconfig_warned = []
def enable_modules(self, modules, debug=False) :

    # Return False if a module cannot be enabled, otherwise True
    import sys

    if sys.platform == "linux2" :

	if not self.has_key('QT5DIR'):
            return False

        if debug:
            modules = [module + "_debug" for module in modules]
        for module in modules:
            if (self['QT5DIR'] == USE_PKG_CONFIG):
                Debug("enabling module %s through pkg-config" % (module), self)
                # Starting directory for headers.  First try 
                # 'pkg-config --variable=headerdir Qt'. If that's empty 
                # (this happens on CentOS 5 systems...), try 
                # 'pkg-config --variable=prefix QtCore' and append '/include'.
                hdir = pc.RunConfig(self, 'pkg-config --variable=headerdir Qt')
                if (hdir == ''):
                    prefix = pc.RunConfig(self, 
                                          'pkg-config --variable=prefix QtCore')
                    if (prefix == ''):
                        print('Unable to build Qt header dir for adding module ' +
                              module)
                        return False
                    hdir = os.path.join(prefix, 'include')

                if pc.CheckConfig(self, 'pkg-config --exists ' + module):
                    # Retrieve LIBS and CFLAGS separately, so CFLAGS can be
                    # added just once (unique=1).  Otherwise projects like
                    # ASPEN which require qt modules many times over end up
                    # with dozens of superfluous CPP includes and defines.
                    cflags = pc.RunConfig(self,
                                          'pkg-config --cflags ' + module)
                    self.MergeFlags(cflags, unique=1)
                    libflags = pc.RunConfig(self,
                                            'pkg-config --libs ' + module)
                    self.MergeFlags(libflags, unique=0)
                else:
                    # warn if we haven't already
                    if not (module in no_pkgconfig_warned):
                        print("Warning: No pkgconfig for Qt5/" + module + 
                              ", doing what I can...")
                        no_pkgconfig_warned.append(module)
                    # Add -l<module>
                    self.Append(LIBS = [module])
                    # Add -I<Qt5HeaderDir>/<module>
                    self.AppendUnique(CPPPATH = [os.path.join(hdir, module)])
                    Debug("qt5.enable_modules appended %s to CPPPATH" %
                          os.path.join(hdir, module), self)
            else:
                Debug("enabling module %s with QT5DIR=%s" %
                      (module, self['QT5DIR']), self)
                # Module library directory can apparently be either
                # <QT5DIR>/lib/<module> or just <QT5DIR>/lib.  Use the
                # longer one if the directory exists, otherwise the shorter
                # one...  Likewise use the lib64 prefix if it exists, since
                # system installations on 64-bit hosts may only be
                # accessible in /usr/lib64/qt5/lib64.  Otherwise resort to
                # the usual 'lib' subdir, which sometimes exists even on
                # x86_64 .
                libpath = os.path.join(self['QT5DIR'], 'lib64')
                if not os.path.exists(libpath):
                    libpath = os.path.join(self['QT5DIR'], 'lib')
                longpath = os.path.join(libpath, module)
                if os.path.isdir(longpath):
                    libpath = longpath
                self.AppendUnique(LIBPATH = [libpath])
		# if this does not look like a system path, add it to
		# RPATH.  This is helpful when different components have
		# been built against differents versions of Qt, but the one
		# specified by this tool is the one that should take
		# precedence.
                if not libpath.startswith('/usr/lib'):
                    self.AppendUnique(RPATH = [libpath])

                hdir = os.path.join(self['QT5DIR'], 'include')
                self.AppendUnique(CPPPATH = [hdir])
                self.AppendUnique(CPPPATH = [os.path.join(hdir, module)])
                self.Append(LIBS = [module])

            # Kluge(?) so that moc can find the QtDesigner headers, necessary
            # at least for Fedora 6 and 7 (and CentOS 5)
            if module == "QtDesigner":
                self.AppendUnique(QT5_MOCFROMHFLAGS =
                                  ['-I', os.path.join(hdir, module)])
            if module == "QtGui":
                self.AppendUnique(CPPDEFINES = ["QT_GUI_LIB"])

            # For QtCore at least, check that compiler can find the
            # library.  Do not propagate any current LIBS, since the
            # configure check does not depend on those, only on the current
            # paths and the compiler.  Otherwise scons will try to build
            # the library targets as part of the configure check, and that
            # causes all kinds of unexpected build behavior...
            skipconfig = self.GetOption('help') or self.GetOption('clean')
            if module == "QtCore" and not skipconfig:
                if not _checkQtCore(self):
                    return False
        return True

    if sys.platform == "win32" :
	if not self.has_key('QT5DIR'):
            return False

        if debug : debugSuffix = 'd'
        else : debugSuffix = ''
        self.Append(LIBS=[lib+'4'+debugSuffix for lib in modules])
        if 'QtOpenGL' in modules:
            self.Append(LIBS=['opengl32'])
        self.AppendUnique(CPPPATH=[ '$QT5DIR/include/' ])
        self.AppendUnique(CPPPATH=[ '$QT5DIR/include/'+module
            for module in modules])
        self.AppendUnique(LIBPATH=['$QT5DIR/lib'])
        
    if sys.platform == "darwin" :
        # Use the frameworks on OSX 
        # Homebrew installs the frameworks in /usr/local/lib.
        self.AppendUnique(FRAMEWORKPATH=['/usr/local/lib',])
        self.AppendUnique(FRAMEWORKS=modules)
        # Add include paths for the modules. One would think that the frameworks
        # would do this, but apparently not.
        for m in modules:
        	self.AppendUnique(CPPPATH=['/usr/local/lib/' + m + '.framework/Headers',])
        
    return True


def exists(env):
    return _detect(env)


