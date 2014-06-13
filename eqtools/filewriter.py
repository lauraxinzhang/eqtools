import scipy 
import scipy.interpolate
import warnings
import time
import core
import matplotlib.pyplot as plt
#import trispline

def gfile(obj, tin, nw=None, nh=None, shot=None, name=None, tunit = 'ms', title='EQTOOLS', nbbbs=100):
 
    if shot is None:
        shot = obj._shot

    timeConvertDict = {'ms':1000.,'s':1.}
    stin = str(int(float(tin)*timeConvertDict[tunit]/timeConvertDict[obj._defaultUnits['_time']]))

    if name is None:
        name = 'g'+str(shot)+'.'+stin

    if nw is None:
        nw = len(obj.getRGrid())

    if nh is None:
        nh = len(obj.getZGrid())

    if len(title) > 10:
        raise ValueError('title is too long')

    header = title+ (11-len(title))*' '+ \
                         time.strftime('%m/%d/%Y')+ \
                         '   '+str(shot)+' '+ stin + tunit
                     
    header = header + (51-len(header))*' '+ '3 '+str(nw)+' '+str(nh)+'\n'
   
    rgrid = scipy.linspace(obj.getRGrid()[0],obj.getRGrid()[-1],nw)
    zgrid = scipy.linspace(obj.getZGrid()[0],obj.getZGrid()[-1],nh)
    rgrid2,zgrid2 = scipy.meshgrid(rgrid,zgrid)
    print(header)

    gfiler =open(name, 'wb')
    gfiler.write(header)
    
    gfiler.write(_fmt([obj.getRGrid()[-1]-obj.getRGrid()[0],
                       obj.getZGrid()[-1]-obj.getZGrid()[0],
                       0.,
                       obj.getRGrid()[0],
                       obj.getZGrid()[-1]/2.+obj.getZGrid()[0]/2.]))
    
    rcent = obj.getMagRSpline()(tin)
    zcent = obj.getMagZSpline()(tin)
    psiLCFS = -1*obj.getCurrentSign()*obj._getLCFSPsiSpline()(tin)

    gfiler.write(_fmt([rcent,
                       zcent,
                       -1*obj.getCurrentSign()*obj._getPsi0Spline()(tin),
                       psiLCFS,
                       0.])) # need to get bzero getter...      

    if obj._tricubic:
        temp = scipy.interpolate.interp1d(obj.getTimeBase(),
                                          obj.getIpCalc(),
                                          kind='cubic',
                                          bounds_error=False)
        Ip = temp(tin)
    else:
        idx = obj._getNearestIdx(tin,obj.getTimeBase())
        Ip = obj.getIpCalc()[idx]
                                          
    gfiler.write(_fmt([Ip,
                       -1*obj.getCurrentSign()*obj._getPsi0Spline()(tin),
                       0.,
                       rcent,
                       0.]))

    gfiler.write(_fmt([zcent,
                       0.,
                       psiLCFS,
                       0.,
                       0.]))
    
    pts0 = scipy.linspace(0.,1.,obj.getRGrid().size) #find original nw
    pts1 = scipy.linspace(0.,1.,nw)
    
    # this needs to be time mapped (sigh)
    if not obj._tricubic: 

        for i in [obj.getF(),
                  obj.getFluxPres(),
                  obj.getFFPrime(),
                  obj.getPPrime()]:

            temp = scipy.interpolate.interp1d(pts0,
                                              scipy.atleast_2d(i)[idx],
                                              kind='nearest',
                                              bounds_error=False)
            gfiler.write(_fmt(temp(pts1).ravel()))

    else:
        tempt = tin*scipy.ones(pts1.shape)
        for i in [obj.getF(),
                  obj.getFluxPres(),
                  obj.getFFPrime(),
                  obj.getPPrime()]:

            temp = scipy.interpolate.RectBivariateSpline(obj.getTimeBase(),
                                                         pts0,
                                                         scipy.atleast_2d(i))
            gfiler.write(_fmt(temp.ev(tempt,pts1).ravel()))


    psiRZ = -1*obj.getCurrentSign()*obj.rz2psi(rgrid2,
                                               zgrid2,
                                               tin)
    gfiler.write(_fmt(psiRZ.ravel())) #spline with new rz grid

    if not obj._tricubic:
        temp = scipy.interpolate.interp1d(pts0,
                                          scipy.atleast_2d(obj.getQProfile())[idx],
                                          kind='nearest',
                                          bounds_error=False)
        
        
    
        gfiler.write(_fmt(temp(pts1).ravel())) 
        
    else:
        temp = scipy.interpolate.RectBivariateSpline(obj.getTimeBase(),
                                                     pts0,
                                                     scipy.atleast_2d(obj.getQProfile()))
    
        gfiler.write(_fmt(temp.ev(tempt,pts1).ravel())) 
    
    # find plasma boundary
    out = findLCFS(rgrid,
                   zgrid,
                   psiRZ,
                   rcent,
                   zcent,
                   psiLCFS,
                   nbbbs=nbbbs)

    #write boundary
    lim = scipy.array(obj.getMachineCrossSection()).T

    gfiler.write('  '+str(int(len(out)))+'   '+str(int(len(lim)))+'\n')

    gfiler.write(_fmt(out.ravel()))
    
    gfiler.write(_fmt(lim.ravel()))

    gfiler.close()
            

def findLCFS(rgrid, zgrid, psiRZ, rcent, zcent, psiLCFS, nbbbs=100):
    plt.ioff()  
    fig = plt.figure()
    cs = plt.contour(rgrid,
                     zgrid,
                     psiRZ,
                     [psiLCFS]) 
    
    splines = []
    for i in cs.collections[0].get_paths():
        temp = i.vertices
        # turn points into polar coordinates about the plasma center
        rvals = scipy.sqrt((temp[:,0] - rcent)**2 + (temp[:,1] - zcent)**2)
        thetvals = scipy.arctan2(temp[:,1] - zcent,temp[:,0] - rcent)
       
        # find all monotonic sections of contour line in r,theta space
        temp = scipy.diff(thetvals)
        idx = 0
        sign = scipy.sign(temp[0])
        for j in xrange(len(temp)-1):
            if (scipy.sign(temp[j+1]) != sign): 
                sign = scipy.sign(temp[j+1])
                #only write data if the jump at the last point is well resolved
                if (j+2-idx > 2):#abs(thetvals[idx]-thetvals[j+1]) < 7*scipy.pi/4) and 
                    splines += [scipy.interpolate.interp1d(thetvals[idx:j+2],
                                                           rvals[idx:j+2],
                                                           kind='linear',
                                                           bounds_error=False,
                                                           fill_value=scipy.inf)]
                idx = j+1
 
        splines += [scipy.interpolate.interp1d(thetvals[idx:len(thetvals)],
                                               rvals[idx:len(thetvals)],
                                               kind='linear',
                                               bounds_error=False,
                                               fill_value=scipy.inf)]
    

    # construct a set of angles about the center, and use the splines
    # to find the closest part of the contour to the center at that
    # angle, this is the LCFS, store value. If no value is found, store
    # an infite value, which is then tossed out.

    outr = scipy.empty((nbbbs,))
    ang = scipy.linspace(-scipy.pi,scipy.pi,nbbbs)
    for i in xrange(nbbbs):
        temp = scipy.inf
        for j in splines:
            pos = j(ang[i])
            if pos < temp:
                temp = pos
        outr[i] = temp

    # remove infinites
    ang = ang[scipy.isfinite(outr)]
    outr = outr[scipy.isfinite(outr)]
    
    #move back to r,z space
    output = scipy.empty((2,len(ang) + 1))
    output[0,:-1] = outr*scipy.cos(ang) + rcent
    output[1,:-1] = outr*scipy.sin(ang) + zcent                   
    output[0,-1] = output[0,0]
    output[1,-1] = output[1,0]

    # turn off plotting stuff
    plt.ion()
    plt.clf()
    plt.close(fig)
    plt.ioff()
    
    return output.T

    
def _fmt(val):
    """ data formatter for gfiles, which doesnt follow normal conventions..."""
    try:
        temp = '0{: 0.8E}'.format(float(val)*10)
        out =''.join([temp[1],temp[0],temp[3],temp[2],temp[4:]])
    except TypeError:
        out = ''
        idx = 0
        for i in val:
            out += _fmt(i)
            idx += 1
            if (idx == 5):
                out+='\n'
                idx = 0
        if (idx != 0):
            out+='\n'
    return out
