#import builtins
import sys,os,itertools, operator
from collections import OrderedDict
import datetime

#import shapely geometry comaptibility functions
#...and rename them fro clarity
import shapely
from shapely.geometry import asShape as geojson2shapely
#import rtree for spatial indexing
import rtree 

#import internal modules 
from . import loader
from . import saver

def ID_generator():
    i = 0 
    while True:
        yield i
        i+=1

class VectorData:
    def __init__(self,filepath=None,type=None,**kwargs):
        self.filepath = filepath
        #type isoptional and will make features ensure that all geometries are of that type
        #if none. type enforcemnt will be based on first geometry found
        self.type = type

        if filepath:
            fields,rows,geometries,crs = loader.from_file(filepath,**kwargs)
        else:
            fields,rows,geometries,crs = [],[],[],"+proj=longlat+ellps=WGS84+datum=WGS84+no_defs"
        
        self.fields = fields
        self._id_generator = ID_generator()

        ids_rows_geoms = itertools.izip(self._id_generator,rows,geometries)
        featureobjs = (Feature(self,row,geom,id=id) for id,row,geom in ids_rows_geoms)
        self.features = OrderedDict([(feat.id,feat) for feat in featureobjs])

        self.crs = crs 
    
    def __len__(self):
        """
        How many features in the data
        """
        return len(self.features)
    
    def __iter__(self):
        """
        Loop through features in order
        """
        for feat in self.features.itervalues():
            yield feat

    def __getitem__(self,i):
        """
        Gett a feature based on its feature id
        """
        if isinstance(i,slice):
            raise Exception("Can only get one feature at a time")
        else:
            return self.features[i]
    
    def __setitem__(self,i,feature):
        """
        set a feature based on its feature id
        """
        if isinstance(i,slice):
            raise Exception("Can only set one feature at a time")
        else:
            self.features[i] = feature

    ##DATA##
    def add_feature(self,row,geometry):
        feature = Feature(self,row,geometry)
        self[feature.id] = feature

    def copy(self):
        new  = VectorData()
        new.fields[field for fileds in self.fields]
        featureobjs = (Feature(new,feat.row,feat.geometry) for feat in self)
        new.features = OrderedDict([(feat.id,feat) for feat in featureobjs])

        if hasattr(self,"spindex"):
            new.spindex = self.spindex.copy()
        return new

    @property
    def bbox(self):
        xmins,ymins,xmaxs,ymaxs = itertools.izip(*(feat.bbox for feat in self))
        xmin ,xmax = min(xmins),max(xmaxs)
        ymin , ymax = max(ymins),max(ymaxs)
        bbox = (xmin,ymin,xmax,ymax)
        return bbox
        

class Feature:
    def __init__(self,data,row,geometry,id=None):
        "geometry must be a geojson dictionary"
        self._data = data
        self.row = list(row)

        self.geometry = geometry.copy()

        #ensure it is same geometry type as parent 
        geotype = self.geometry["type"]
        if self._data.type:
            if "Point" in geotype and self._data.type == "Point":
                pass
            elif "Linestring" in geotype and self._data.type =="Linestring":
                pass
            elif "Polygon" in geotype and self._data.type == "Polygon":
                pass
            else:
                raise Exception("Each feature geometry must be of the same type as the file it is attached to")
        else:
            self._data.type = self.geometry["type"].replace("Multi", "")

        if id == None:
            id = next(self._data._id_generator)
            self.id = id

        bbox = geometry.get("bbox")
        self._cached_bbox = bbox

    def __getitem__(self,i):
        if isinstance(i,(str,unicode)):
            i = self._data.fields.index(i)
        return self.row[i]

    def __setitem__(self,i,setvalue):
        if isinstance(i,(str,unicode)):
            i = self._data.fields.index(i)
        self.row[i] = setvalue

    def get_shapely(self):
        return geojson2shapely(self.geometry)

    def copy(self):
        geoj = self.geometry
        if self._cached_bbox:
            geoj["bbox"] = self._cached_bbox
            return Feature(self._data,self.row,geoj)
    
    @property
    def bbox(self):
        if not self._cached_bbox:
            geotype =self.geometry["type"]
            coords = self.geometry["coordinates"]

            if geotype == "Point":
                x,y = coords
                bbox = [x,y,x,y]
            elif geotype in ("MultiPoint","LineString"):
                xs,ys = itertools.izip(*coords)
                bbox = [min(xs),min(ys),max(xs),min(ys)]
            elif  geotype == "MulltiLineString":
                xs = [x for line in coords for x,y in line]
                ys = [y for line in coords for x,y in line]
                bbox = [min(xs),min(ys),max(xs),max(ys)]
            elif geotype == "Polygon":
                exterior = coords[0]
                xs,ys = itertools.izip(*exterior)
                bbox = [min(xs),min(ys),max(xs),max(ys)]
            elif geotype == "Multipolygon":
                xs = [x for poly in coords for x,y in poly[0]]
                ys = [y for poly in coords for x,y in poly[0]]
                bbox = [min(xs),min(ys),max(xs),max(ys)]
            self._cached_bbox = bbox
        return self._cached_bbox

    
