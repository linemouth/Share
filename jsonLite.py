from collections import OrderedDict
import io, math, re

class RegexReader:
    @property
    def HasNext(self):
        #if(isinstance(self.stream, io.IOBase)):
        #    position = self.stream.tell()
        return len(self.stream) > 0
    def __init__(self, stream):
        self.stream = stream
    def __repr__(self):
        return "RegexReader[{}]".format(len(self.stream))
    def TryReadRegex(self, pattern):
        match = pattern.match(self.stream)
        if(match != None):
            self.stream = self.stream[match.end():]
        return match
class SerializerOptions:
    def __init__(self):
        self.keyQuotes = True
        self.scope = 0
        self.indent = "    "
        self.newline = "\n"
        self.bracesSpacing = "newline"
        self.bracketsSpacing = "space"
        self.commaSpacing = "space"
        self.spaceAfterColon = True
        self.includeNull = True
        self.order = []
class Json(OrderedDict):
    nameNeedsQuotesRegex_ = re.compile(r"[\s:]", re.MULTILINE)
    keyRegex_ = re.compile(r"\s*(?:(?P<quote>\"|')(?P<quotedKey>.*?)(?P=quote)|(?P<key>\w+))\s*:\s*", re.MULTILINE)
    stringRegex_ = re.compile(r"\s*(?P<quote>\"|')(?P<value>.*?)(?<!\\)(?P=quote)\s*,?\s*", re.MULTILINE)
    hexRegex_ = re.compile(r"\s*0[xX](?P<value>[0-9a-fA-F]+)\s*,?\s*", re.MULTILINE)
    intRegex_ = re.compile(r"\s*(?P<value>[\+-]?(?:\d+))\s*,?\s*", re.MULTILINE)
    floatRegex_ = re.compile(r"\s*\+?(?P<value>-?(?:\d+\.\d*|\d*\.\d+)(?:[eE]-?\d+)?)\s*,?\s*", re.MULTILINE)
    keywordRegex_ = re.compile(r"\s*(?P<value>[-\w]+)\s*,?\s*", re.MULTILINE)
    listStartRegex_ = re.compile(r"\s*\[\s*", re.MULTILINE)
    listEndRegex_ = re.compile(r"\s*\]\s*,?\s*", re.MULTILINE)
    objectStartRegex_ = re.compile(r"\s*\{\s*", re.MULTILINE)
    objectEndRegex_ = re.compile(r"\s*\}\s*,?\s*", re.MULTILINE)
    commentRegex_ = re.compile(r"\s*(?://\s*(?P<line>.*?)/s*$|/\*\s*(?P<block>.*?)\s*\*/)\s*", re.MULTILINE)
    keywords_ = {
        "null": None,
        "undefined": None,
        "true": True,
        "false": False,
        "nan": math.nan,
        "infinity": math.inf,
        "-infinity": -math.inf
    }
    def __init__(self):
        super().__init__()
        self.comments = {}
    def __repr__(self):
        return "{}[{} items]".format(self.__class__.__name__, len(self))
    def __eq__(self, other):
        if(self.__class__ != other.__class__):
            return False
        elif(self.keys() != other.keys()):
            return False
        else:
            for key, value in self.items():
                if(other[key] != value):
                    return False
        return True
    def AddComment(key, comment):
        if(key not in self.comments):
            self.comments[key] = [comment]
        else:
            self.comments[key].append(comment)
    def TryParseKey(reader):
        match = reader.TryReadRegex(Json.keyRegex_)
        if(match != None):
            return match.group("quotedKey") or match.group("key")
        return None
    @classmethod
    def Parse(cls, text):
        reader = RegexReader(text)
        result = cls.ParseObject(reader, reader.TryReadRegex(Json.objectStartRegex_) != None)
        return result
    @classmethod
    def ParseObject(cls, reader, requireClosure):
        data = cls()
        key = None
        while(reader.HasNext):
            # Parse comments
            match = reader.TryReadRegex(Json.commentRegex_)
            if(match != None):
                data.AddComment(key, match.group("line") or match.group("block"))
            else:
                # Parse key/value
                key = Json.TryParseKey(reader)
                if(key != None):
                    value = Json.ParseValue(reader)
                    data[key] = value
                # Parse closure
                elif(requireClosure):
                    if(reader.TryReadRegex(Json.objectEndRegex_) != None):
                        break
                    raise Exception("Could not find object closure.")
                # Complain
                else:
                    raise Exception("Unexpected token")
        return data
    def ParseList(reader):
        list = []
        while (True):
            if(reader.TryReadRegex(Json.listEndRegex_) != None):
                return list
            else:
                list.append(Json.ParseValue(reader))
    def ParseValue(reader):
        match = reader.TryReadRegex(Json.stringRegex_)
        if(match != None):
            return match.group("value")
        match = reader.TryReadRegex(Json.hexRegex_)
        if(match != None):
            return int(match.group("value"), 16)
        match = reader.TryReadRegex(Json.floatRegex_)
        if(match != None):
            return float(match.group("value"))
        match = reader.TryReadRegex(Json.intRegex_)
        if(match != None):
            return int(match.group("value"))
        match = reader.TryReadRegex(Json.objectStartRegex_)
        if(match != None):
            return Json.ParseObject(reader, True)
        match = reader.TryReadRegex(Json.listStartRegex_)
        if(match != None):
            return Json.ParseList(reader)
        match = reader.TryReadRegex(Json.keywordRegex_)
        if(match != None):
            keyword = match.group("value").lower()
            if(keyword in Json.keywords_):
                return Json.keywords_[keyword]
            else:
                raise Exception("Unknown keyword: '{}'".format(reader.text.split("\n")[0]))
        raise Exception("Unexpected token")
    def Serialize(data, options = SerializerOptions()):
        text = Json.FormatObjectStart(options)
        firstItem = True
        keys = data.keys()
        sortedKeys = [key for key in options.order if key in keys]
        keys = sortedKeys + list(keys - set(sortedKeys))
        for key in keys:
            value = data[key]
            if value != None or options.includeNull:
                if(firstItem):
                    firstItem = False
                elif options.commaSpacing == "space":
                    text += ", "
                elif options.commaSpacing == "newline":
                    text += ",\n" + Json.FormatIndent(options)
                else:
                    text += ","
                text += Json.FormatKey(key, options)
                text += Json.FormatValue(value, options)
        return text + Json.FormatObjectEnd(options)
    def FormatObjectStart(options):
        text = "{"
        options.scope += 1
        if(options.bracesSpacing == "space"):
            text += " "
        elif(options.bracesSpacing == "newline"):
            text += "\n" + Json.FormatIndent(options)
        return text
    def FormatObjectEnd(options):
        options.scope -= 1
        if(options.bracesSpacing == "space"):
            return " }"
        elif(options.bracesSpacing == "newline"):
            return "\n" + Json.FormatIndent(options) + "}"
        else:
            return "}"
    def FormatIndent(options):
        text = ""
        for i in range(options.scope):
            text += options.indent
        return text
    def FormatKey(key, options):
        needQuotes = options.keyQuotes or Json.nameNeedsQuotesRegex_.search(key) != None
        text = None
        if(needQuotes):
            quote = "\""
            escape = False
            if("\"" in key):
                if("'" in key):
                    escape = True
                else:
                    quote = "'"
            if(escape):
                key = key.replace("\"", "\\\"")
            text = quote + key + quote
        else:
            text = key
        return text + ": " if options.spaceAfterColon else ":"
    def FormatValue(value, options):
        if(value == None):
            text = "null"
        elif(type(value) is bool):
            text = "true" if value else "false"
        elif(value == math.nan):
            text = "nan"
        elif(value == math.inf):
            text = "Infinity"
        elif(value == -math.inf):
            text = "-Infinity"
        elif(type(value) is str):
            quote = '"'
            if(quote in value):
                if("'" in value):
                    value = value.replace('"', '\\"')
                else:
                    quote = "'"
            text = quote + value + quote
        elif(type(value) is int or type(value) is float):
            text = "{}".format(value)
        elif(type(value) is list):
            options.scope += 1
            separator = ","
            if(options.commaSpacing == "space"):
                separator = ", "
            elif(options.commaSpacing == "newline"):
                separator = ",\n" + Json.FormatIndent(options)
            items = []
            for item in value:
                items.append(Json.FormatValue(item, options))
            text = "[" + separator.join(items) + "]"
            options.scope -= 1
        elif(issubclass(value.__class__, OrderedDict) or type(value) is object):
            text = Json.Serialize(value, options)
        else:
            raise Exception("Cannot serialize unsupported type '{}'.".format(value.__class__.__name__))
        return text




