

import os
import yaml
import logging
import imp

from misc import ERROR,appendPath


logger = logging.getLogger("ezcluster.plugins")

class Plugin:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.groomer = None
        
    def getSchema(self):
        f = os.path.join(self.path, "schema.yml")
        if os.path.exists(f):
            return yaml.load(open(f))
        else:
            return {}
    
    def getConfigSchema(self):
        f = os.path.join(self.path, "config-schema.yml")
        if os.path.exists(f):
            return yaml.load(open(f))
        else:
            return {}
    
    def groom(self, model):
        rolesPath = appendPath(self.path, "roles")
        if os.path.exists(rolesPath):
            model['data']["rolePaths"].add(rolesPath)
        codeFile = appendPath(self.path, "groomer.py")
        if os.path.exists(codeFile):
            logger.debug("Will load '{0}' as python code".format(codeFile))
            self.groomer = imp.load_source(self.name, codeFile)
            if hasattr(self.groomer, "groom"):
                method = getattr(self.groomer, "groom")
                logger.debug("FOUND '{0}' method".format(str(method)))
                method(self, model)

    def dump(self, model, dumper):
        # Try to lookup in groomer.py
        if self.groomer != None:
            if hasattr(self.groomer, "dump"):
                method = getattr(self.groomer, "dump")
                logger.debug("FOUND '{0}' method".format(str(method)))
                method(self, model, dumper)
        # Lookup a specific dump file (DEPRECATED 
        """
        codeFile = appendPath(self.path, "dump.py")
        if os.path.exists(codeFile):
            logger.debug("Will load '{0}' as python code".format(codeFile))
            dumperCode = imp.load_source(self.name, codeFile)
            if hasattr(dumperCode, "dump"):
                method = getattr(dumperCode, "dump")
                logger.debug("FOUND '{0}' method".format(str(method)))
                method(self, model, dumper)
        """


    def walk(self, targetFileByName):
        """ Enrich the targetFileByName structure with file from this plugin """
        #logger.debug(self.path + "<----")
        snippetsPath = appendPath(self.path, "snippets")
        pref = len(snippetsPath) + 1
        for dirpath, dirnames, filenames in os.walk(snippetsPath):  # @UnusedVariable
            #logger.debug("dirpath:{}  dirnames:{}  filename:{}".format(dirpath, dirnames, filenames))
            for filename in filenames:
                #logger.debug(filename)
                if not filename == ".gitignore":
                    sourceFile = os.path.join(dirpath, filename)
                    targetFileName = sourceFile[pref:]
                    if targetFileName.count(".") < 2:
                        # We pass throught non super-suffixed files
                        order = 0
                        ftype = "txt"
                    else:
                        # Handle the type and eventual suffix (Used as short comment)
                        pos = targetFileName.rfind(".")
                        suffix = targetFileName[pos+1:]
                        targetFileName = targetFileName[:pos]
                        pos = suffix.find("-")
                        if pos != -1:
                            ftype = suffix[:pos]
                            suffix = suffix[pos+1:]
                        else:
                            ftype = suffix
                            suffix = None
                        # Now order number
                        pos = targetFileName.rfind(".")
                        idx = targetFileName[pos+1:]
                        targetFileName = targetFileName[:pos]
                        try:
                            order  = int(idx)
                        except ValueError:
                            ERROR("'{0}' is not a valid file part".format(sourceFile))
                            
                    logger.debug(sourceFile + "-->" + targetFileName + "(" + str(idx) + ")")
                        
                    if targetFileName not in targetFileByName:
                        targetFileByName[targetFileName] = {}
                        #targetFileByName[targetFileName].name = targetFileName
                        targetFileByName[targetFileName]['fileParts'] = []
                    fp = {}
                    fp['name'] = sourceFile
                    fp['order'] = order
                    fp['plugin'] = self.name
                    fp['type'] = ftype
                    if suffix != None:
                        fp["suffix"] = suffix
                    targetFileByName[targetFileName]['fileParts'].append(fp)
                    #targetFileByName[targetFileName].fileParts.insert(0, fp)   # To exercise the sort




def lookupPlugin(plugin, pluginsPath):
    for path in pluginsPath:
        p = os.path.join(path, plugin)
        if os.path.exists(p):
            return Plugin(plugin, p)
    ERROR("Unable to find plugin '{}'".format(plugin))
    

def buildPlugins(cluster, pluginsPath):
    plugins = []
    if "plugins" in cluster:
        for m in cluster['plugins']:
            plugins.append(lookupPlugin(m, pluginsPath))
    return plugins

validType = set(["txt", "j2", "jj2"])
                
def buildTargetFileByName(plugins):
    "Build a map by file name, where each file is an array of file parts"
    targetFileByName = {}
    for plugin in plugins:
        plugin.walk(targetFileByName)
    # For each target file, sort parts by order. And check validity
    for name, targetFile in targetFileByName.iteritems():
        targetFile['fileParts'] = sorted(targetFile['fileParts'], key = lambda fp: fp['order'])
        refType = targetFile["fileParts"][0]['type']
        if refType not in validType:
            ERROR("Invalid type '{0}' for file '{1}'. (plugin:'{2}', target:'{3}'). Only {4} are allowed".format(refType, name, targetFile["fileParts"][0]['plugin'], targetFile["fileParts"][0]['name'], str(validType)))
        for fp in targetFile['fileParts']:
            if fp['type'] != refType:
                ERROR("Type mismatch for file target:'{}'. All type for a target must be same ('{}' != '{}')".format(name, fp['type'], refType))
    return targetFileByName
