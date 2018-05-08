import numpy as np
import pickle
import matplotlib.pyplot as plt

def bspleval(x, knots, coeffs, order, debug=True):
    '''
    Evaluate a B-spline at a set of points.

    Parameters
    ----------
    x : list or ndarray
        The set of points at which to evaluate the spline.
    knots : list or ndarray
        The set of knots used to define the spline.
    coeffs : list of ndarray
        The set of spline coefficients.
    order : int
        The order of the spline.

    Returns
    -------
    y : ndarray
        The value of the spline at each point in x.
    '''

    k = order
    t = knots
    m = np.alen(t)
    npts = np.alen(x)
    B = np.zeros((m-1,k+1,npts))

    if debug:
        print('k=%i, m=%i, npts=%i' % (k, m, npts))
        print('t=', t)
        print('coeffs=', coeffs)

    ## Create the zero-order B-spline basis functions.
    for i in range(m-1):
        B[i,0,:] = np.float64(np.logical_and(x >= t[i], x < t[i+1]))

    if (k == 0):
        B[m-2,0,-1] = 1.0

    ## Next iteratively define the higher-order basis functions, working from lower order to higher.
    for j in range(1,k+1):
        for i in range(m-j-1):
            if (t[i+j] - t[i] == 0.0):
                first_term = 0.0
            else:
                first_term = ((x - t[i]) / (t[i+j] - t[i])) * B[i,j-1,:]

            if (t[i+j+1] - t[i+1] == 0.0):
                second_term = 0.0
            else:
                second_term = ((t[i+j+1] - x) / (t[i+j+1] - t[i+1])) * B[i+1,j-1,:]

            B[i,j,:] = first_term + second_term
        B[m-j-2,j,-1] = 1.0

    if debug:
        plt.figure()
        for i in range(m-1):
            plt.plot(x, B[i,k,:])
        plt.title('B-spline basis functions')

    ## Evaluate the spline by multiplying the coefficients with the highest-order basis functions.
    y = np.zeros(npts)
    for i in range(m-k-1):
        y += coeffs[i] * B[i,k,:]

    if debug:
        plt.figure()
        plt.plot(x, y)
        plt.title('spline curve')
        plt.show()

    return(y)



def estimated_template(pe,start=0,stop=500,step=0.2):
    pkl_file = open('templates_bspline.p', 'rb')
    dict_template = pickle.load(pkl_file)
    xs = np.linspace(start,stop, (stop-start)*1./step)
    coeffs = []
    for coef in range(len(dict_template['coeff_sample'])):
        coeffs.append(dict_template['spline_coeff_func_pe'][coef](float(pe)))

    return xs,bspleval(xs, dict_template['knots_sample'], np.array(coeffs), 5, debug=False)


def plot_pes_template(list_pe):
    plt.figure()
    for pe in list_pe:
        x_template,y_template = estimated_template(pe)
        plt.plot(x_template, y_template, '--', lw=2, label='$f(N_{\gamma}=%d)$'%pe)
    plt.legend()
    plt.show()

def amplitude():
    pes,gain,meas = [],[],[]
    for logpe in np.arange(1.,4.,0.1):
        pe = 10.**logpe
        x_template, y_template = estimated_template(pe, start=0, stop=500)
        pes+=[pe]
        gain+=[np.max(y_template) / pe /4.72]
        meas+=[np.max(y_template) /4.72 ]
    plt.figure()
    plt.plot(pes, gain)
    plt.xscale("log")
    plt.show()
    plt.figure()
    plt.xscale("log")
    plt.plot(pes, meas)
    plt.show()

def consecutive(data, stepsize=1):
    return np.split(data, np.where(np.diff(data) != stepsize)[0]+1)

def integral():
    pes,gain,meas,integ,integ_2 = [],[],[],[],[]
    for logpe in np.arange(1.,4.,0.1):
        pe = 10.**logpe
        x_template, y_template = estimated_template(pe, start=0, stop=500)
        pes+=[pe]
        gain+=[np.sum(y_template[:80])/5.]
        meas+=[np.max(y_template)/4.72 ]
        integ+=[np.sum(y_template[:80])/5./22. ]
        if meas[-1]>570:
            good = consecutive(np.where(y_template>0)[0])
            h = np.zeros((len(good),))
            for i,g in enumerate(good):
                h[i] = np.sum(y_template[(g,)]) / 5. / 22.64
            integ_2 += [np.max(h)]
        else:
            integ_2+=[integ[-1]]
    print(pes, meas)
    plt.figure()
    plt.plot(pes, gain)
    plt.show()
    plt.figure()
    plt.plot(pes, integ,label='Integral')
    plt.plot(pes, integ_2,label='Integral until 0')
    plt.plot(pes, meas,label='Peak amplitude')
    plt.ylim(10.,10000.)
    plt.xlim(10.,10000.)
    plt.xlabel('$\mathrm{N_{true}(p.e.)}$')
    plt.ylabel('$\mathrm{N_{evaluated}(p.e.)}$')
    plt.legend()
    plt.show()


def plot_pe(pe):
    plt.figure()
    plt.xlabel('ADC')
    plt.ylabel('A.U.')
    plt.ylim(-400.,4096.)
    plt.xlim(0.,300.)
    x_template,y_template = estimated_template(pe,start=0,stop=500)
    #y_template[0:-11] = y_template[10:-1]
    plt.plot(x_template, y_template, 'r', lw=2, label='$f(N_{\gamma}=%d),G=%0.3f$'%(pe,np.max(y_template)/pe))
    plt.legend()
    plt.show()


def dump_int_dat(pe):
    f = open('template_%s.dat'%str(pe),'w')
    x_template,y_template = estimated_template(pe,start=0,stop=291,step=1)
    # Convert from PE to mV ; "Conversion factor 1PE = 2.4 mV"
    y_template = y_template*(-0.4285714285714286)
    f.write('-8.0 0.0\n')
    f.write('-7.0 0.0\n')
    f.write('-6.0 0.0\n')
    f.write('-5.0 0.0\n')
    f.write('-4.0 0.0\n')
    f.write('-3.0 0.0\n')
    f.write('-2.0 0.0\n')
    f.write('-1.0 0.0\n')
    f.write('0.0 0.0\n')
    for i in range(x_template.shape[0]):
        f.write('%0.1f %f\n'%(x_template[i],y_template[i]))
    f.close()

plot_pes_template([2000, 3000, 4000,5000, 6000, 7000,10000]) #,5,10,20,100,1000,4000])

dump_int_dat(3000)
dump_int_dat(4000)
dump_int_dat(5000)
dump_int_dat(6000)
dump_int_dat(7000)
dump_int_dat(8000)




amplitude()
#integral()
