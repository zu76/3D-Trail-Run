import numpy as np, math, os
_cache={}
def _tile(la,lo,d="hgt"):
    k=(la,lo)
    if k not in _cache:
        p=os.path.join(d,"N%02dE%03d.hgt"%(la,lo))
        a=np.fromfile(p,dtype=">i2").reshape(3601,3601).astype(np.float32)
        a[a<-1000]=np.nan
        _cache[k]=a
    return _cache[k]
def sample(lat,lon,d="hgt"):
    lat=np.asarray(lat,float); lon=np.asarray(lon,float)
    out=np.empty(lat.shape,np.float32)
    tla=np.floor(lat).astype(int); tlo=np.floor(lon).astype(int)
    for la in np.unique(tla):
        for lo in np.unique(tlo):
            m=(tla==la)&(tlo==lo)
            if not m.any(): continue
            A=_tile(la,lo,d)
            r=(la+1-lat[m])*3600.0; c=(lon[m]-lo)*3600.0
            r0=np.clip(np.floor(r).astype(int),0,3599); c0=np.clip(np.floor(c).astype(int),0,3599)
            fr=r-r0; fc=c-c0
            out[m]=(A[r0,c0]*(1-fr)*(1-fc)+A[r0+1,c0]*fr*(1-fc)
                   +A[r0,c0+1]*(1-fr)*fc+A[r0+1,c0+1]*fr*fc)
    return out
def grid(lat0,lat1,lon0,lon1,n=600,d="hgt"):
    R=6371000.0; latm=(lat0+lat1)/2
    W=math.radians(lon1-lon0)*R*math.cos(math.radians(latm))
    H=math.radians(lat1-lat0)*R
    if W>=H: nx=n; ny=max(2,int(round(n*H/W)))
    else: ny=n; nx=max(2,int(round(n*W/H)))
    LO,LA=np.meshgrid(np.linspace(lon0,lon1,nx),np.linspace(lat1,lat0,ny))
    return sample(LA,LO,d),(W,H,nx,ny)
