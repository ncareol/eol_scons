import os
import re
from symlink import MakeSymLink
from SCons.Node.FS import Dir,File
from SCons.Script import Builder,Execute
import SCons.Defaults
import SCons.Scanner.Prog


def GetArchLibDir(env):
    # ARCHLIBDIR can be used if the user wants to install libraries
    # to a special directory for the architecture, like lib64
    #
    # It is tempting to pass clean=False and help=False to this Configure
    # context, but that might change the paths to targets which need to be
    # cleaned or are specified in help variables.

    sconf = env.Clone(LIBS=[]).Configure()
    libdir = 'lib'
    if sconf.CheckTypeSize('void *',expect=8,language='C'):
        libdir = 'lib64'
    env['ARCHLIBDIR'] = libdir
    sconf.Finish()
    return libdir


def SharedLibrary3Emitter(target,source,env):

    """
    If 'xxx' was the target name passed to the SharedLibrary3 builder,
    then the target passed to this emitter is libxxx.so.X.Y, assuming
    $SHLIBPREFIX='lib', is the value of the prefix parameter when this
    builder was created, and the suffix is '.so.X.Y', the concatenation of
    $SHLIBSUFFIX + '.' + $SHLIBMAJORVERSION + '.' + $SHLIBMINORVERSION

    This emitter returns three targets for the given sources,
    in this order:
        libxxx.so, libxxx.so.X, and libxxx.so.X.Y
    """

    fullname = str(target[0])

    # Use reg expression substitution to remove the '.X.Y' from 'libxxx.so.X.Y'
    try:
        # Convert '.' to '\.' for exact matching.
        versionsuffixre = re.sub(r'\.',r'\\.',
                '.' + env['SHLIBMAJORVERSION'] + '.' + env['SHLIBMINORVERSION'] + '$')
    except KeyError:
        print 'Cannot find SHLIBMAJORVERSION or SHLIBMINORVERSION env variables'

    libname = re.sub(versionsuffixre,'', fullname)
    # print "fullname=" + fullname + ", libname=" + libname

    soname = libname + '.' + env['SHLIBMAJORVERSION']

    return ([libname,soname,fullname],source)

def SharedLibrary3Action(target,source,env):

    """
    Action to build a shared library and symbolic links.

    The targets generated by the above emitter are:
    target[0] = libxxx.so       short name
    target[1] = libxxx.so.X     soname
    target[2] = libxxx.so.X.Y   full library

    SHLINKCOM is the action used by the SharedLibrary builder.
    """

    soname = os.path.basename(target[1].path)

    env = env.Clone()
    env.Append(SHLINKFLAGS=['-Wl,-soname=' + soname])

    # Execute the shared library action to build the full library
    if env.Execute(env.subst('$SHLINKCOM',target=target[2],source=source)):
        raise SCons.Errors.BuildError(node=target[2],
                errstr="%s failed" % env.subst('$SHLINKCOM'))

    # env.Execute(env.subst('$SHLINKCOM',target=target[2],source=source), env.subst('$SHLINKCOMSTR',target=target[2],source=source))

    # Now use the action of the SymLink builder to create
    # symbolic links from libxxx.so.X.Y to libxxx.so.X and libxxx.so
    MakeSymLink([target[0]],[target[2]],env)
    MakeSymLink([target[1]],[target[2]],env)
    return 0

def SharedLibrary3Install(env,target,source,**kw):

    """
    Install source library to a library subdirectory of target.
    If env["ARCHLIBDIR"] is defined, the source will be installed
    to target/$ARCHLIBDIR, otherwise to target/lib.

    See the discussion for SharedLibrary3 about how library versions 
    are handled.

    source[0] is the target returned from SharedLibrary3, which is the
    short name of the library: libxxx.so

    If source[1] exists, it is assumed to be the second target
    returned from SharedLibrary3, which is the "soname":
    libxxx.so.X

    If source[2] exists, it is assumed to be the third target
    returned from SharedLibrary3, which is the full library name:
    libxxx.so.X.Y

    This installer will copy libxxx.so.X.Y to target/lib[64],
    and then create symbolic links on the target lib directory:
        libxxx.so -> libxxx.so.X.Y
        libxxx.so.X -> libxxx.so.X.Y
    """

    # add passed keywords to environment
    env = env.Clone(**kw)

    if env.has_key("ARCHLIBDIR"):
        targetDir = env.Dir(target + '/' + env['ARCHLIBDIR'])
    else:
        targetDir = env.Dir(target + '/lib')

    # libname = source[0].path
    libname = str(source[0])

    if len(source) > 1:
        soname = str(source[1])
    else:
        try:
            soname = libname + '.' + env['SHLIBMAJORVERSION']
        except KeyError:
            print 'Cannot find SHLIBMAJORVERSION env variable'
            return None

    if len(source) > 2:
        fullname = str(source[2])
    else:
        try:
            fullname = soname + '.' + env['SHLIBMINORVERSION']
        except KeyError:
            print 'Cannot find SHLIBMINORVERSION env variable'
            return None
        # print "SharedLibrary3Install, fullname=" + fullname

    nodes = []
    tgt = env.Install(targetDir,fullname)
    nodes.extend(tgt)

    tgt = targetDir.File(os.path.basename(libname))
    nodes.extend(env.SymLink(tgt,fullname))

    tgt = targetDir.File(os.path.basename(soname))
    nodes.extend(env.SymLink(tgt,fullname))
    
    # return list of targets which can then be used in an Alias
    return nodes

def generate(env):
    """ 
    Builder and Installer for shared libraries and their associated symbolic links.

    Usage:
        # GitInfo tool can be used to set REPO_TAG in environment
        env.GitInfo("include/revision.h", "#")

        # If REPO_TAG is in the form "vX.Y" or "VX.Y", where X and Y are
        # integers, then this generate function will set
            env["SHLIBMAJORVERSION"] = X
            env["SHLIBMINORVERSION"] = Y

        # If not using GitInfo, set SHLIBMAJORVERSION and SHLIBMINORVERSION
        # by hand
        if not env.has_key("REPO_TAG"):
            env["SHLIBMAJORVERSION"] = "3"
            env["SHLIBMINORVERSION"] = '5'

        # if modules in libfoo.so use symbols from libbar.so, add LIBS=['bar']
        libs = env.SharedLibrary3('foo',['foo.c'],
            LIBS=['bar'],LIBPATH=['/opt/bar/lib'])
        env.SharedLibrary3Install('/opt/foo',libs)

    The SharedLibrary3 builder above will create one library and two
    symbolic links to it:
    1. actual library file, libfoo.so.3.5
    2. symbolic link: libfoo.so.3 -> libfoo.so.3.5
    3. symbolic link: libfoo.so -> libfoo.so.3.5

    The SharedLibrary3Install statement will install the library and
    its links on /opt/foo/$ARCHLIBDIR.

    If ARCHLIBDIR is not pre-defined it will set to 'lib64' on 64 bit systems
    'lib' on 32 bit systems.

    For a reference on Linux conventions for shared library names see
    http://tldp.org/HOWTO/Program-Library-HOWTO/shared-libraries.html

    The usual convention is that the full library name is something like:
        libxxx.so.X.Y
    Where X is the major version number of the binary API and Y is the minor version.

    The SONAME of the library is
        libxxx.so.X
    The basic library name, used when initially linking executables, is
        libxxx.so

    Under linux, libxxx.so.X.Y is typically the actual library file,
    and libxxx.so.X and libxxx.so are symbolic links.

    The idea is that two libraries with the same name, same major
    number, but differing minor number, implement the same binary API, and
    that a library with a new minor number could replace the old
    without breaking executable programs that depend on the library.

    From the man page of ld, discussing the -soname option:
    -soname=name
        When creating an ELF shared object, set the internal DT_SONAME field to
        the specified name.  When an executable is linked with a shared object
        which has a DT_SONAME field, then when the executable is run the dynamic
        linker will attempt to  load  the  shared object specified by the
        DT_SONAME field rather than the using the file name given to the linker.

    If the SONAME of a library contains just the major version number, and a
    a symbolic link exists with a name equal to the SONAME, pointing
    to the real library file, then a new library file could be installed
    with a different minor number, and the symbolic link updated to point
    to the new library, without re-linking executables.  This will only work
    if the binary APIs of libraries with the same major number are compatible.

    The SONAME of a library can be seen with
        objdump -p libxxx.so | grep SONAME

    ldd lists the SONAMEs of the libraries that a program was linked against.
    rpmbuild uses the same tools as ldd, and creates dependencies for
    executables based on the SONAMEs of the linked libraries.

    If the library has a SONAME, then the basic library name, libxxx.so,
    without major and minor numbers, is only used when linking executables
    with the -lxxx option.  That is why symbolic link .so's, without major
    and minor numbers, are sometimes found only in -devel RPMs.

    To create the above three libraries with this builder, set "REPO_TAG",
    or "SHLIBMAJORVERSION" and "SHLIBMINORVERSION" in the environment:

        env['REPO_TAG'] = 'v3.4'
        # or
        env['SHLIBMAJORVERSION'] = '3'
        env['SHLIBMINORVERSION'] = '4'

        lib = env.SharedLibrary3('xxx',objects)

    This builder will set the -soname in the real library file, and the other
    two will be symbolic links.

    To install the library and the symbolic links to a destination:

        env.SharedLibrary3Install('/opt/mystuff',lib)

    If the environment token ARCHLIBDIR not defined, it will be set to
    "lib64" on 64 bit systems and "lib" on 32.

    In the install step, the libraries will be installed in
    /opt/mystuff/env['ARCHLIBDIR'].

    As of this writing, this builder has only been tested on Linux.
    Support for other architectures needs to be added as necessary.

    One potential issue is whether there should be dots between the
    library suffix and the major and minor version numbers in the
    library file name.
    """

    if not env.has_key("SHLIBMAJORVERSION") and env.has_key("REPO_TAG"):
        rev = re.match("[Vv]([0-9]+)\.([0-9]+)",env["REPO_TAG"])
        if rev:
            env["SHLIBMAJORVERSION"] = rev.group(1)
            env["SHLIBMINORVERSION"] = rev.group(2)


    # Special builder for shared libraries.
    # Some of these build parameters were stolen from the definition
    # of the SharedLibrary builder in /usr/lib/scons/SCons/Tool/__init__.py
    builder = Builder(
            action=[SCons.Defaults.SharedCheck,SharedLibrary3Action],
            emitter=SharedLibrary3Emitter,
            prefix='$SHLIBPREFIX',
            suffix='${SHLIBSUFFIX}.${SHLIBMAJORVERSION}.${SHLIBMINORVERSION}',
            target_scanner=SCons.Scanner.Prog.ProgramScanner(),
            src_suffix='$SHOBJSUFFIX',
            src_builder='SharedObject'
            )
    env.Append(BUILDERS = {"SharedLibrary3": builder})
    env.AddMethod(SharedLibrary3Install)
    if not env.has_key('ARCHLIBDIR'):
        GetArchLibDir(env)


def exists(env):
    return 1
