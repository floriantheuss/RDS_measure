import numpy as np
from numpy import sqrt
from lmfit.models import LorentzianModel, LinearModel
from lmfit import Model, Parameter
from RDS_measure.resonance_detector.load_frequency_sweep import FreqSweepData, FreqSweep
import matplotlib.pyplot as plt


class FitResonances:
    def __init__ (self, sweep, 
                  f0_guess_array, gamma_guess_array, A_guess_array=None, phi_guess_array=None,
                  c0_guess_array=None, c1_guess_array=None, m0_guess_array=None, m1_guess_array=None,
                  mulitplicator_fit_window=5, number_automated_fits=5, plot_fits_bool=False):
        self.sweep             = sweep
        self.f0_guess_array    = f0_guess_array
        self.gamma_guess_array = gamma_guess_array
        self.A_guess_array     = A_guess_array
        if self.A_guess_array is None: self.A_guess_array = np.zeros(len(self.f0_guess_array))
        self.phi_guess_array   = phi_guess_array
        if self.phi_guess_array is None: self.phi_guess_array = np.zeros(len(self.f0_guess_array))
        self.c0_guess_array    = c0_guess_array
        if self.c0_guess_array is None: self.c0_guess_array = np.zeros(len(self.f0_guess_array))
        self.c1_guess_array    = c1_guess_array
        if self.c1_guess_array is None: self.c1_guess_array = np.zeros(len(self.f0_guess_array))
        self.m0_guess_array    = m0_guess_array
        if self.m0_guess_array is None: self.m0_guess_array = np.zeros(len(self.f0_guess_array))
        self.m1_guess_array    = m1_guess_array
        if self.m1_guess_array is None: self.m1_guess_array = np.zeros(len(self.f0_guess_array))
        

        self.multiplicator_fit_window = mulitplicator_fit_window
        self.number_automated_fits    = number_automated_fits

        # create arrays to store fit results
        self.f0_array    = np.zeros(len(f0_guess_array))
        self.gamma_array = np.zeros(len(f0_guess_array))
        self.A_array     = np.zeros(len(f0_guess_array))
        self.phi_array   = np.zeros(len(f0_guess_array))
        self.c0_array    = np.zeros(len(f0_guess_array))
        self.c1_array    = np.zeros(len(f0_guess_array))
        self.m0_array    = np.zeros(len(f0_guess_array))
        self.m1_array    = np.zeros(len(f0_guess_array))
        self.fmin_array  = np.zeros(len(f0_guess_array))
        self.fmax_array  = np.zeros(len(f0_guess_array))
        
        # if True all fits will be plotted after being executed "self.number_automated_fits" times
        self.plot_fits_bool = plot_fits_bool


    def complexLorentzian (self, f, f0, gamma, A, phi, c0, c1, m0, m1):
        # this defines a complex Lorentzian with a constant and linear background
        # phi = phi/(2*np.pi)%1 # this is just so that the value for phi stays between 0 and 1 to make sure it doesn't get arbitrarily large
        # phi = phi%(2*np.pi) # restrict phi to be between 0 and 2*pi
        phi = phi/360*2*np.pi # phi in degrees
        # L = A * np.exp(phi*1j) / (f-f0 + gamma/2*1j) + c0 + c1*1j + (m0 + m1*1j)*f
        L = A * np.exp(phi*1j) / (gamma/2 - (f-f0)*1j) + c0 + c1*1j + (m0 + m1*1j)*f
        return L

    def fit_individual_Lorentzian (self, f0_guess=None, gamma_guess=None, A_guess=0, phi_guess=45, c0_guess=0, c1_guess=0, m0_guess=0, m1_guess=0):
        if f0_guess is None:
            f0_guess = self.f0_guess_array[0]
        if gamma_guess is None:
            gamma_guess = self.gamma_guess_array[0]
        # prepare data for fit
        f, X, Y  = self.sweep.freq, self.sweep.X, self.sweep.Y
        fit_mask = (f>=f0_guess-self.multiplicator_fit_window*np.absolute(gamma_guess)) & (f<=f0_guess+self.multiplicator_fit_window*np.absolute(gamma_guess))
        y_fit    = X[fit_mask] + Y[fit_mask]*1j
        x_fit    = f[fit_mask]

        # prepare fit model and parameters
        if A_guess == 0: A_guess = max(np.absolute(y_fit))*gamma_guess
        model  = Model(self.complexLorentzian)
        params = model.make_params(f0=f0_guess, gamma=gamma_guess, A=A_guess, phi=phi_guess,
                                   c0=c0_guess, c1=c1_guess, m0=m0_guess, m1=m1_guess)
        # params['phi'].set(min=0)
        # params['phi'].set(max=180)

        # perform fit and return fit parameters
        out    = model.fit(y_fit, params=params, f=x_fit)
        best_vals = out.best_values
        f0, gamma, A, phi, c0, c1, m0, m1 = best_vals['f0'], best_vals['gamma'], best_vals['A'], best_vals['phi'], best_vals['c0'], best_vals['c1'], best_vals['m0'], best_vals['m1']
        
        return [f0, gamma, A, phi, c0, c1, m0, m1, np.min(x_fit), np.max(x_fit)]
    

    def fit_multiple_Lorentzians (self, f0_guess_array, gamma_guess_array, A_guess_array, phi_guess_array, c0_guess_array, c1_guess_array, m0_guess_array, m1_guess_array):
        for ii, _ in enumerate(f0_guess_array):
            try:
                fit_result  = self.fit_individual_Lorentzian (f0_guess_array[ii], gamma_guess_array[ii], A_guess_array[ii], phi_guess_array[ii],
                                                              c0_guess_array[ii], c1_guess_array[ii], m0_guess_array[ii], m1_guess_array[ii])
                self.f0_array[ii]    = fit_result[0]
                self.gamma_array[ii] = fit_result[1]
                self.A_array[ii]     = fit_result[2]
                self.phi_array[ii]   = fit_result[3]
                self.c0_array[ii]    = fit_result[4]
                self.c1_array[ii]    = fit_result[5]
                self.m0_array[ii]    = fit_result[6]
                self.m1_array[ii]    = fit_result[7]
                self.fmin_array[ii]  = fit_result[8]
                self.fmax_array[ii]  = fit_result[9]
            except:
                self.f0_array[ii]    = np.nan
                self.gamma_array[ii] = np.nan
                self.A_array[ii]     = np.nan
                self.phi_array[ii]   = np.nan
                self.c0_array[ii]    = np.nan
                self.c1_array[ii]    = np.nan
                self.m0_array[ii]    = np.nan
                self.m1_array[ii]    = np.nan
                self.fmin_array[ii]  = np.nan
                self.fmax_array[ii]  = np.nan


    def repeat_multiple_Lorentzians_fit (self):
        self.fit_multiple_Lorentzians(self.f0_guess_array, self.gamma_guess_array, self.A_guess_array, self.phi_guess_array,
                                      self.c0_guess_array, self.c1_guess_array, self.m0_guess_array, self.m1_guess_array)
        for _ in np.arange(self.number_automated_fits-1):
            self.fit_multiple_Lorentzians(self.f0_array, self.gamma_array, self.A_array, self.phi_array,
                                          self.c0_array, self.c1_array, self.m0_array, self.m1_array)
        if self.plot_fits_bool:
            self.plot_fits()

    def plot_fits (self):
        f, X, Y  = self.sweep.freq, self.sweep.X, self.sweep.Y
        for ii, _ in enumerate(self.f0_array):
            mask = (f>=self.fmin_array[ii]) & (f<=self.fmax_array[ii])
            ffit, xfit, yfit = f[mask], X[mask], Y[mask]
            plt.figure()
            plt.plot(ffit, xfit, ls='', marker='o')
            plt.plot(ffit, yfit, ls='', marker='o')
            fit = self.complexLorentzian(ffit, self.f0_array[ii], self.gamma_array[ii], self.A_array[ii], self.phi_array[ii],
                                         self.c0_array[ii], self.c1_array[ii], self.m0_array[ii], self.m1_array[ii])
            plt.plot(ffit, np.real(fit), ls='--', color='black')
            plt.plot(ffit, np.imag(fit), ls='--', color='black')
            plt.show()