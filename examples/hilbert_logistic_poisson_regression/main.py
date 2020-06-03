from __future__ import print_function
import numpy as np
import bayesiancoresets as bc
from scipy.optimize import minimize
from inference import nuts, rhat, hmc
import time
import sys, os
import argparse

#TODO use PyStan for inference
#TODO copy riemann_logistic_poisson_regression example
#make it so we can import models/etc from parent folder
sys.path.insert(1, os.path.join(sys.path[0], '../common'))
import mcmc

parser = argparse.ArgumentParser(description="Runs Hilbert logistic or poisson regression (employing coreset contruction) on the specified dataset")
parser.add_argument('model', type=str, choices=["lr","poiss"], help="The regression model to use. lr refers to logistic regression, and poiss refers to poisson regression.") #must be one of linear regression or poisson regression
parser.add_argument('dnm', type=str, help="The name of the dataset on which to run regression")
parser.add_argument('anm', type=str, help="The algorithm to use for solving sparse non-negative least squares as part of Hilbert coreset construction - should be one of GIGA / FW / RND") #TODO: find way to make this help message autoupdate with new methods
parser.add_argument('ID', type=int, help="The trial number - used to initialize random number generation (for replicability)")
#TODO: make mcmc params command-line args

arguments = parser.parse_args()
dnm = arguments.dnm
anm = arguments.anm
ID = arguments.ID
model = arguments.model

algdict = {'GIGA':bc.snnls.GIGA, 'FW':bc.snnls.FrankWolfe, 'RND':bc.snnls.UniformSampling}
lrdnms = ['synth_lr', 'phishing', 'ds1', 'synth_lr_large', 'phishing_large', 'ds1_large']
prdnms = ['synth_poiss', 'biketrips', 'airportdelays', 'synth_poiss_large', 'biketrips_large', 'airportdelays_large']
if model=="lr":
  from model_lr import *
elif model=="poiss":
  from model_poiss import *

np.random.seed(ID)

#should be command line arguments - and also need to be saved in results file name!
mcmc_steps = 10000 #total number of MH steps
mcmc_burn = 1000
projection_dim = 500 #random projection dimension
Ms = np.unique(np.logspace(0, 3, 10, dtype=int))

pbar = True #progress bar display flag
step_size_init = 0.001
n_leap = 15
target_a = 0.8
mcmc_alg = hmc #nuts

print('Loading dataset '+dnm)
X,Y,Z, Zt, D = load_data('../data/'+dnm+'.npz')

if not os.path.exists('results/'):
  os.mkdir('results')  

if not os.path.exists('results/'+dnm+'_laplace.npz'):
  print('Computing Laplace approximation for '+dnm)
  t0 = time.process_time()
  res = minimize(lambda mu : -log_joint(Z, mu, np.ones(Z.shape[0]))[0], Z.mean(axis=0)[:D], jac=lambda mu : -grad_th_log_joint(Z, mu, np.ones(Z.shape[0]))[0,:])
  mu = res.x
  cov = -np.linalg.inv(hess_th_log_joint(Z, mu, np.ones(Z.shape[0]))[0,:,:])
  t_laplace = time.process_time() - t0
  np.savez('results/'+dnm+'_laplace.npz', mu=mu, cov=cov, t_laplace=t_laplace)
else:
  print('Loading Laplace approximation for '+dnm)
  lplc = np.load('results/'+dnm+'_laplace.npz')
  mu = lplc['mu']
  cov = lplc['cov']
  t_laplace = lplc['t_laplace']

#generate a sampler based on the laplace approx 
sampler = lambda sz, w, pts : np.atleast_2d(np.random.multivariate_normal(mu, cov, sz))
projector = bc.BlackBoxProjector(sampler, projection_dim, log_likelihood)

full_samples = mcmc.sampler(dnm, X, Y, mcmc_steps, stan_representation, cache_folder = "caching/")
#TODO FIX SAMPLER TO NOT HAVE TO DO THIS
full_samples = np.hstack((full_samples[:, 1:], full_samples[:, 0][:,np.newaxis]))

cputs = np.zeros(Ms.shape[0])
csizes = np.zeros(Ms.shape[0])
Fs = np.zeros(Ms.shape[0])

print('Running coreset construction / MCMC for ' + dnm + ' ' + anm + ' ' + str(ID))
t0 = time.process_time()
alg = bc.HilbertCoreset(Z, projector, snnls = algdict[anm])
t_setup = time.process_time() - t0
t_alg = 0.
for m in range(Ms.shape[0]):
  print('M = ' + str(Ms[m]) + ': coreset construction, '+ anm + ' ' + dnm + ' ' + str(ID))
  #this runs alg up to a level of M; on the next iteration, it will continue from where it left off
  t0 = time.process_time()
  itrs = (Ms[m] if m == 0 else Ms[m] - Ms[m-1])
  alg.build(itrs)
  t_alg += time.process_time()-t0
  wts, pts, idcs = alg.get()


  print('M = ' + str(Ms[m]) + ': MCMC')
  # Here we would like to measure the time it would take to run mcmc on our coreset.
  # however, this is particularly challenging - stan's mcmc implementation doesn't work on 
  # the weighted likelihoods we use in our coresets. And our inference.py nuts implementation
  # (which does work on weighted likelihoods) is not as efficient or reliable as stan.
  curX = X[idcs, :]
  curY = Y[idcs]
  t0 = time.process_time()
  mcmc.sampler(dnm, curX, curY, mcmc_steps, stan_representation, weights=wts)
  t_alg_mcmc = time.process_time()-t0   

  print('M = ' + str(Ms[m]) + ': CPU times')
  cputs[m] = t_laplace + t_setup + t_alg #+ t_alg_mcmc
  print('M = ' + str(Ms[m]) + ': coreset sizes')
  csizes[m] = wts.shape[0]
  print('M = ' + str(Ms[m]) + ': F norms')
  gcs = np.array([ grad_th_log_joint(Z[idcs, :], full_samples[i, :], wts) for i in range(full_samples.shape[0]) ])
  gfs = np.array([ grad_th_log_joint(Z, full_samples[i, :], np.ones(Z.shape[0])) for i in range(full_samples.shape[0]) ])
  Fs[m] = (((gcs - gfs)**2).sum(axis=1)).mean()
np.savez_compressed('results/'+dnm+'_'+anm+'_results_'+str(ID)+'.npz', Ms=Ms, Fs=Fs, cputs=cputs, csizes=csizes)
