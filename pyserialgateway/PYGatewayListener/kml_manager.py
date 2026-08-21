'''
KMLMapManager: builds and maintains the daily .kml map document used for
Google Earth GPS node mapping.
'''
import xml.dom.minidom
import lxml.etree
import pykml.parser

class KMLMapManager():
    '''XML format document object containing functions to generate KML-type map file on Google Earth'''
    def __init__(self):    
        self.map_file = xml.dom.minidom.Document()
        self.name_iter_start = b'<name>'
        self.name_iter_end = b'</name>'
        
    def add_style_to_placemark(self, *args):
        '''
        Should be called only in the ini_run INIT stage.
        Includes one icon style and shape into the inventory of the main Document.
        '''
        self.docElement, self.styleID, self.stylehref = args
        styleElement = self.map_file.createElementNS(self.styleID, 'Style')
        styleElement.setAttribute('id', self.styleID)
        self.docElement.appendChild(styleElement)
        iconstyleElement = self.map_file.createElement('IconStyle')
        styleElement.appendChild(iconstyleElement)
        iconlinkElement = self.map_file.createElement('Icon')
        iconstyleElement.appendChild(iconlinkElement)
        iconlinkText = self.map_file.createTextNode(self.stylehref)
        iconlinkElement.appendChild(iconlinkText)
    
    def add_placemark(self, *args):
        '''
        Includes one node data under the Coordinates writing pointer of the Document.
        Should only be called after the ini_run INIT stage has been completed. 
        '''
        node_name, node_description, node_lat, node_long = args
        placemarkElement = self.map_file.createElement('Placemark')
        nameElement = self.map_file.createElement('name')
        placemarkElement.appendChild(nameElement)
        nameText = self.map_file.createTextNode(node_name)
        nameElement.appendChild(nameText)
        
        typeElement = self.map_file.createElement('description')
        placemarkElement.appendChild(typeElement)
        node_description_str = node_description + ' - geolocation'
        typeText = self.map_file.createTextNode(node_description_str)
        typeElement.appendChild(typeText)
        
        styleURL = None
        if node_description == '#G0':
            pass
        elif node_description == '#G0!':
            styleURL = self.stylelist[0][0]
        elif node_description == '#G0-':
            styleURL = self.stylelist[1][0]
        elif node_description == '#G0|V|':
            styleURL = self.stylelist[2][0]
            
        if styleURL != None:
            styleElement = self.map_file.createElement('styleUrl')
            placemarkElement.appendChild(styleElement)
            styledescription = '#' + styleURL
            styleText = self.map_file.createTextNode(styledescription)
            styleElement.appendChild(styleText)
        
        pointElement = self.map_file.createElement('Point')
        placemarkElement.appendChild(pointElement)
        coordinates = node_long+','+node_lat+','+'0'
        coorElement = self.map_file.createElement('coordinates')
        coorElement.appendChild(self.map_file.createTextNode(coordinates))
        pointElement.appendChild(coorElement)
        
        return placemarkElement
    
    def writetokmlfile(self):
        '''
        Calling this function will commit any data that is written under any writing pointer of the Document into the KML physical file.
        '''
        kmlFile = open(self.kmlpathname, 'wb')
        kmlFile.write(self.map_file.toprettyxml(encoding='utf-8'))
    
    def remove_whitespace_nodes(self, documentFile, unlink=False):
        '''
        Recursive function to remove all text-type whitespace when reassembling existing data within a pre-existing Document object.
        '''
        remove_list = []
        for child in documentFile.childNodes:
            if child.nodeType == xml.dom.Node.TEXT_NODE and not child.data.strip():
                remove_list.append(child)
            elif child.hasChildNodes:
                _ = self.remove_whitespace_nodes(child,unlink)
        for node in remove_list:
            node.parentNode.removeChild(node)
            if unlink:
                node.unlink()
        return documentFile
    
    def inherit_old_document_info(self, *args):
        old_data_list = []
        self.kmlpathname, self.stylelist = args
        existingDocumentFile = xml.dom.minidom.parse(self.kmlpathname)
        self.map_file = self.remove_whitespace_nodes(existingDocumentFile,False)
        newDocumentElement = self.map_file.getElementsByTagName('Document')[0]
        with open(self.kmlpathname) as f:
            doc = pykml.parser.parse(f)
        data_string = lxml.etree.tostring(doc)
        while data_string.find(self.name_iter_start) != -1:
            data_index_start = data_string.find(self.name_iter_start)
            data_index_end = data_string.find(self.name_iter_end)
            node_data = (data_string[data_index_start:data_index_end+len(self.name_iter_end)]).replace(self.name_iter_start, b'').replace(self.name_iter_end, b'')
            data_string = data_string[data_index_end+len(self.name_iter_end):]
            try:
                _ = int(node_data.decode('utf-8'), 16)
                old_data_list.append(node_data.decode('utf-8'))
            except:
                pass
        return newDocumentElement, old_data_list
                
    def ini_run(self, *args):
        '''
        Call-able INIT process for KMLMapManager. Creates the document headers and formats required to insert coordinates data.
        It then returns the Coordinates writing pointer for the Document to the caller. 
        '''
        self.kmlpathname, self.stylelist = args
        kmlElement = self.map_file.createElementNS('http://earth.google.com/kml/2.0', 'kml')
        kmlElement.setAttribute('xmlns','http://earth.google.com/kml/2.0')
        self.map_file.appendChild(kmlElement)
        documentElement = self.map_file.createElement('Document')
        kmlElement.appendChild(documentElement)
        for i in range(0, len(self.stylelist)):
            self.add_style_to_placemark(documentElement, self.stylelist[i][0], self.stylelist[i][1])
        return documentElement

