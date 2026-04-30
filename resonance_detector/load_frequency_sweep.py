import numpy as np
from scipy.signal import butter, filtfilt
from dataclasses import dataclass
from scipy.interpolate import interp1d
from numpy import sqrt, sin, cos, arctan2


@dataclass
class FreqSweepData:
    freq: np.array
    X: np.array
    Y: np.array


class FreqSweep:
    def __init__ (self, path, nyq_low=0.00001, nyq_high=1):
        self.path = path
        self.raw_sweep  = self.load_data()
        self.int_sweep  = self.interpolate_sweep(self.raw_sweep)
        self.filt_sweep = self.remove_background(self.int_sweep, nyq_low=nyq_low, nyq_high=nyq_high)

# changes here
    def load_data (self):
        if self.path.endswith('.dat') or self.path.endswith('.txt'):
            data = np.loadtxt(self.path, delimiter=',') # the raw
            f = data[:,0]
            x = data[:,1]
            y = data[:,2]
        elif self.path.endswith('.npz'):
            data = np.load(self.path)
            f = data['freq (Hz)'] 
            x = data['Real part (V)']
            y = data['Imaginary part (V)']
            
        mask      = np.argsort(f)
        f, x, y   = f[mask], x[mask], y[mask]
        return FreqSweepData(f,x,y)

    def interpolate_sweep(self, sweep, delta_f=None):
        f_min, f_max = np.min(sweep.freq), np.max(sweep.freq)
        # df = abs(f_max - f_min)/np.shape(sweep.freq)[0]
        df = np.median(sweep.freq[1:]-sweep.freq[:-1])
        if not delta_f is None: df = delta_f
        N = int((f_max-f_min)/df)

        interp_f = np.linspace(f_min, f_max, N)
        Xint, Yint = interp1d(sweep.freq, sweep.X)(interp_f), interp1d(sweep.freq, sweep.Y)(interp_f)
        return FreqSweepData(interp_f, Xint, Yint)

    def remove_background(self, sweep, nyq_low=0.00001, nyq_high=1):
        f, X, Y = sweep.freq, sweep.X, sweep.Y
        df = abs(np.max(f)-np.min(f))/np.shape(f)[0]

        # high pass filter

        nyq = 2*nyq_low*df
        fb, fa = butter(3, nyq, btype= 'hp', analog= False)
        Xlp = filtfilt(fb, fa, X)
        Ylp = filtfilt(fb, fa, Y)

        # low pass filter after high pass filter
        nyq = 2*nyq_high*df
        if nyq>=1:
            Xbp, Ybp = Xlp, Ylp
        else:
            fb, fa = butter(3, nyq, btype= 'lp', analog= False)
            Xbp = filtfilt(fb, fa, Xlp)
            Ybp = filtfilt(fb, fa, Ylp)

        return FreqSweepData(f, Xbp, Ybp)
