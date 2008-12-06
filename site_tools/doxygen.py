# -*- python -*-

import os
import string
import SCons
import SCons.Node
import SCons.Util
from SCons.Node import FS
import fnmatch
from fnmatch import fnmatch

def tagfile (node):
    """
    Construct the name of the tag file for the source directory
    in the given node.
    """
    top = node.get_dir().Dir('#')
    if node.get_dir() == top:
        subdir = 'root'
    else:
        subdir = str(node.get_dir().get_path(top))
    qtag = string.replace(subdir, '/', '_') + '.tag'
    return qtag


def apidocsdir(env):

    subdir = str(env.Dir('.').get_path(env.Dir('#')))
    subdir = string.replace(subdir, '/', '_')
    return os.path.join(env['APIDOCSDIR'],subdir)


def ddebug(env):
    return env.has_key('DOXYGEN_DEBUG')


def CheckMissingHeaders(subdir, doxfiles, ignores):

    found = []
    # print "Subdir: ", subdir
    # print "Files: ", doxfiles
    # print "Ignores: ", ignores
    for root, dirs, files in os.walk(subdir):
        files = filter(lambda f: 
                       not fnmatch(f, "moc_*")
                       and not fnmatch(f, "ui_*")
                       and not fnmatch(f, "*.ui*")
                       and not fnmatch(f, "uic_*")
                       and fnmatch(f, "*.h"), files)
        found += [os.path.normpath(os.path.join(root, f)) for f in files]
        if '.svn' in dirs:
            dirs.remove('.svn')

    known = [ os.path.normpath(os.path.join(subdir, p))
              for p in doxfiles+ignores ]
    missing = [ f for f in found if f not in known ]
    missing.sort()
    if len(missing) > 0:
        print "Header files missing in "+subdir+":"
        print "  "+"\n  ".join(missing)
    return missing


def Doxyfile_Emitter (target, source, env):
    """
    Modify the target and source lists to use the defaults if nothing
    else has been specified.

    Dependencies on external HTML documentation references are also
    appended to the source list.
    """
    if ddebug(env):
        print "doxyfile_emitter:"
    try:
        source.extend ([env.File (env['DOXYFILE_FILE'])])
        if ddebug(env):
            print "added Doxyfile dependency ", str(source[len(source)-1])
    except KeyError:
        pass
    outputdir = str(target[0].get_dir())
    if ddebug(env):
        print ("DOXREF=", env['DOXREF'])
    for tag in env['DOXREF']:
        i = string.find(tag,':')
        if i > 0:
            continue
        qtag=string.replace(tag,"/","_")
        indexpath="%s/../%s/html/index.html" % (outputdir, qtag)
        source.append (env.File(indexpath))
        if ddebug(env):
            print "added doxref dependency: ", str(source[len(source)-1])

    return target, source
    

def Doxyfile_Builder (target, source, env):
    """
    Generate a standard Doxyfile for the Doxygen builder.  This builder
    expects one target, the name of the doxygen config file to generate.
    The generated config file sets directory parameters relative to the
    target directory, so it expects Doxygen to run in the same directory as
    the config file.  The documentation output will be written under
    that same directory.

    This builder uses these environment variables:

    DOXYFILE_FILE

    The name of a doxygen config file that will be used as the basis for
    the generated configuration.  This file is copied into the destination
    and then appended according to the DOXYFILE_TEXT and DOXYFILE_DICT
    settings.

    DOXYFILE_TEXT

    This should hold verbatim Doxyfile configuration text which will be
    appended to the generated Doxyfile, thus overriding any of the default
    configuration settings.
                        
    DOXYFILE_DICT

    A dictionary of Doxygen configuration parameters which will be
    translated to Doxyfile form and included in the Doxyfile, after the
    DOXYFILE_TEXT settings.  Parameters which specify files or directory
    paths should be given relative to the source directory, then this
    target adjusts them according to the target location of the generated
    Doxyfile.

    The order of precedence is DOXYFILE_DICT, DOXYFILE_TEXT, and
    DOXYFILE_FILE.  In other words, parameter settings in DOXYFILE_DICT and
    then DOXYFILE_TEXT override all others.  A few parameters will always
    be enforced by the builder over the DOXYFILE_FILE by appending them
    after the file, such as OUTPUT_DIRECTORY, GENERATE_TAGFILE, and
    TAGFILES.  This way the template Doxyfile generated by doxygen can
    still be used as a basis, but the builder can still control where the
    output gets placed.  If any of the builder settings really need to be
    overridden, such as to put output in unusual places, then those
    settings can be placed in DOXYFILE_TEXT or DOXYFILE_DICT.

    DOXYFILE_IGNORES

    If given, this is a list of header file names which have been
    excluded explicitly from doxygen input.  The builder will check for
    any header files which are not either in the builder source or in
    the list of ignores.  Those header files will be reported as missing
    and the build will fail.

    Here are examples of some of the Doxyfile configuration parameters
    which typically need to be set for each documentation target.  Unless
    set explicitly, they are given defaults in the Doxyfile.
    
    PROJECT_NAME        Title of project, defaults to the source directory.
    PROJECT_VERSION     Version string for the project.  Defaults to 1.0

    """ 

    topdir = target[0].Dir('#')
    subdir = source[0].get_dir()
    docsdir = str(target[0].get_dir())

    if env.has_key('DOXYFILE_IGNORES'):
        ignores = env['DOXYFILE_IGNORES']
        if CheckMissingHeaders(subdir.get_path(env.Dir('#')),
                               [s.get_path(subdir) for s in source], 
                               ignores):
            return -1

    doxyfile = None
    try:
        doxyfile = env.File (env['DOXYFILE_FILE'], subdir)
    except KeyError:
        pass

    try:
        os.makedirs(docsdir)
    except:
        if not os.access(docsdir, os.W_OK): throw

    print docsdir + " exists"

    dfile = file(str(target[0]),"w")
    # These are defaults that any of the customization methods can override
    dfile.write("""
SOURCE_BROWSER         = YES
INPUT                  = .
GENERATE_HTML          = YES
GENERATE_LATEX         = YES
PAPER_TYPE             = letter
PDF_HYPERLINKS         = YES
USE_PDFLATEX           = YES
GENERATE_RTF           = NO
GENERATE_MAN           = NO

# Allow source code to ifdef out sections which cause warnings from
# doxygen, like explicit template instantiations and recursive class
# templates.
PREDEFINED = DOXYGEN

# 
# Specifically disable extracting private class members and file static
# members, for the case of generating documentation for only the public
# interface of a library.  Instead require individual directories to
# override those as needed.
#
EXTRACT_ALL	       = YES
EXTRACT_STATIC	       = NO
EXTRACT_PRIVATE	       = NO

CLASS_GRAPH            = YES
COLLABORATION_GRAPH    = YES
INCLUDE_GRAPH          = YES
INCLUDED_BY_GRAPH      = YES
GRAPHICAL_HIERARCHY    = YES
REFERENCED_BY_RELATION = NO
REFERENCES_RELATION = NO

""")

    dot_path = env.WhereIs("dot")
    if not dot_path:
        ourpath = []
        if env.has_key('OPT_PREFIX'):
            ourpath.append("%s/bin" % (env['OPT_PREFIX']))
        ourpath.append("/net/opt_lnx/local_fc3/bin")
        dot_path = env.WhereIs("dot", ourpath)
    if dot_path:
        dfile.write("DOT_PATH = %s\n" % os.path.dirname(dot_path))

    # These are defaults which can be overridden by the DOXYFILE_TEXT
    # or DOXYFILE_DICT sections below.
    #
    dfile.write("PROJECT_NAME           = %s\n" % subdir)
    dfile.write("PROJECT_NUMBER         = \"Version 0.1\"\n")

    # Further customizations which can override the settings above.
    if doxyfile:
        ifile = file(doxyfile.path)
        dfile.write (ifile.read())

    # The rest are not defaults.  They are required for things to be put
    # into the right places, thus they are last.
    #
    dfile.write("INPUT                  = \\\n")
    for s in source:
        if not doxyfile or s.path != doxyfile.path:
            dfile.write ("%s \\\n" % s.get_path())
            
    dfile.write ("\n")
    outputdir=docsdir
    dfile.write("OUTPUT_DIRECTORY       = %s\n" % outputdir)
    dfile.write("HTML_OUTPUT            = html\n")
    dfile.write("LATEX_OUTPUT           = latex\n")
    dfile.write("RTF_OUTPUT             = rtf\n")
    dfile.write("MAN_OUTPUT             = man\n")
    dfile.write("GENERATE_TAGFILE       = %s\n" % \
                os.path.join(outputdir, tagfile(source[0])))

    # Parse DOXREF for references to other tag files, internal and
    # external.  Each name in the tag reference refers to the full path of
    # the part of source tree it comes from.  That way all tag files and
    # subdirectories under the documentation directory will be unique.  The
    # names are flattened by replacing slashes with underscoers, so the
    # path for references between local documentation will always be
    # obvious, just '../<tagname>/html'.

    # If the tag file already exists, then use it as is.  If the docpath is
    # also explicitly given, then use that as is too.  Otherwise use
    # doxytag to generate the tag file from an external source given the
    # path to the html files.

    doxref = env['DOXREF']
    print "Parsing DOXREF for tag references: ", doxref
    tagfiles={}
    for tag in doxref:
        i = string.find(tag,':')
        qtag=tag
        if i > 0:
            qtag=tag[0:i]
            docpath=tag[i+1:]
            tagpath=qtag
            if os.path.exists(tagpath):
                tagfiles[tag] = "%s=%s" % (tagpath, docpath)
                print "Using explicit doxref: "+tagfiles[tag]
                continue

        qtag=string.replace(qtag,"/","_")
        tagdir="%s/../%s" % (outputdir, qtag)
        tagpath="%s/%s.tag" % (tagdir, qtag)
        docpath="../../%s/html" % (qtag)
        tagfiles[tag] = "%s=%s" % (tagpath, docpath)

        # Check for external tag reference and generate if necessary
        if i > 0:
            docpath=tag[i+1:]
            toptagpath=tagpath
            topdocpath=os.path.join(docsdir, docpath)
            toptagdir=os.path.join(tagdir)
            if os.access(toptagpath, os.R_OK):
                print "+ %s exists." % toptagpath
            else:
                print "+ Creating tag file %s (%s)." % (tagpath, docpath)
                try:
                    print "mkdir ", toptagdir
                    os.makedirs(toptagdir)
                except:
                    if not os.access(toptagdir, os.W_OK): raise
                os.symlink (docpath, "%s/html" % tagdir)
                doxytag = "doxytag -t %s %s" % (tagpath, docpath)
                print doxytag
                os.system (doxytag)
        
    if len(tagfiles) > 0:
        dfile.write("TAGFILES = %s\n" % string.join(tagfiles.values()))

    # The last of the customizations.  They have to go here for the case
    # of generating output in unusual locations, where it's up to the
    # caller of the builder to set the target correctly.
    #
    dfile.write(env['DOXYFILE_TEXT'])

    for k, v in env['DOXYFILE_DICT'].iteritems():
        dfile.write ("%s = \"%s\"\n" % (k, str(v)))

    dfile.close()
    return None


def doxyfile_message (target, source, env):
    return "creating Doxygen config file '%s'" % target[0]

doxyfile_variables = [
    'DOXYFILE_TEXT',
    'DOXYFILE_DICT',
    'DOXYFILE_FILE',
    'DOXREF'
    ]

doxyfile_action = SCons.Action.Action( Doxyfile_Builder, doxyfile_message,
                                       doxyfile_variables )

doxyfile_builder = SCons.Builder.Builder( action = doxyfile_action,
                                          emitter = Doxyfile_Emitter )


def Doxygen_Emitter (target, source, env):

    """

    Add the output HTML index file as the doxygen target, representative of
    all of the files which will be generated by doxygen.  The first (and
    only) source should be the Doxyfile, and the output is expected to go
    under that directory.
    
    If an explicit target location has been specified (as in it hasn't
    defaulted to be the same as the source), then use that target.

    """
    outputdir = str(source[0].get_dir())
    t = target
    if str(target[0]) == str(source[0]):
        t = env.File(os.path.join (outputdir, "html", "index.html"))
        if ddebug(env):
            print "doxygen_emitter: target set to ", str(t)
    return t, source
    

doxygen_action = SCons.Action.Action ([ '$DOXYGEN_COM'])

doxygen_builder = SCons.Builder.Builder( action = doxygen_action,
                                         emitter = Doxygen_Emitter )

def Apidocs (env, source, **kw):
    target=os.path.join(apidocsdir(env),'Doxyfile')
    doxyfile = env.Doxyfile(target=target, source=source, **kw)
    tdoxygen = env.Doxygen(source=[doxyfile], **kw)
    return tdoxygen

def ApidocsIndex (env, source, **kw):
    doxyconf = """
OUTPUT_DIRECTORY       = apidocs
HTML_OUTPUT            = .
RECURSIVE              = NO
SOURCE_BROWSER         = NO
ALPHABETICAL_INDEX     = NO
GENERATE_LATEX         = NO
GENERATE_RTF           = NO
GENERATE_MAN           = NO
GENERATE_XML           = NO
GENERATE_AUTOGEN_DEF   = NO
ENABLE_PREPROCESSING   = NO
CLASS_DIAGRAMS         = NO
HAVE_DOT               = NO
GENERATE_HTML          = YES
"""
    kw['DOXYFILE_TEXT'] = doxyconf
    df = env.Doxyfile (target="%s/Doxyfile" % env['APIDOCSDIR'],
                       source=source, **kw)
    dx = env.Doxygen (target="%s/index.html" % env['APIDOCSDIR'],
                      source=[df], **kw)
    return dx

from SCons.Script import Environment


def AppendDoxref(env, ref):
    if not env.has_key('DOXREF'):
        env['DOXREF'] = [ref]
    else:
        env['DOXREF'].append(ref)
    if ddebug(env):
        print ("Appended",ref,"; DOXREF=", env['DOXREF'])


def SetDoxref(env, name, tagfile, url):
    env[name] = env.File(env.subst(tagfile)).get_abspath() + ":" + url


def generate(env):
    """Add builders and construction variables for DOXYGEN."""
    # print "doxygen.generate(%s)" % env.Dir('.').get_path(env.Dir("#"))
    env['BUILDERS']['Doxyfile'] = doxyfile_builder
    env['BUILDERS']['Doxygen'] = doxygen_builder
    dict = env.Dictionary()
    dict.setdefault('DOXREF',[])
    dict.setdefault('DOXYFILE_TEXT', "")
    dict.setdefault('DOXYFILE_DICT', {})
    dict.setdefault('DOXYGEN', 'doxygen')
    dict.setdefault('DOXYGEN_FLAGS', '')
    dict.setdefault('DOXYGEN_COM', '$DOXYGEN $DOXYGEN_FLAGS $SOURCE')
    dict.setdefault('APIDOCSDIR', '#apidocs')
    # Add convenience wrappers
    Environment.Apidocs = Apidocs
    Environment.ApidocsIndex = ApidocsIndex
    Environment.AppendDoxref = AppendDoxref
    Environment.SetDoxref = SetDoxref


def exists(env):
    return env.Detect ('doxygen')
