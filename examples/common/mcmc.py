import numpy as np
import pystan
import os
import pickle as pk
import time

def build_model(cache_folder, modelName, model_code):
  if not os.path.exists(os.path.join(cache_folder, modelName)): 
      print('STAN: building model')
      sm = pystan.StanModel(model_code=model_code)
      f = open(os.path.join(cache_folder, modelName),'wb')
      pk.dump(sm, f)
      f.close()
  else:
      f = open(os.path.join(cache_folder, modelName),'rb')
      sm = pk.load(f)
      f.close()
  return sm

def sampler(dnm, X, Y, N_samples, stan_representation, cache_folder = None, chains=1, control={'adapt_delta':0.9, 'max_treedepth':15}, verbose=True):

  if cache_folder and not os.path.exists(cache_folder):
    os.mkdir(cache_folder)

  if cache_folder and os.path.exists(cache_folder+dnm+'_samples.npy'):
    print("Using cached samples for " + dnm)
    return np.load(cache_folder+dnm+'_samples.npy')
  else:
    print('No MCMC samples found -- running STAN')
    print('STAN: loading data')
    Y[Y == -1] = 0 #convert to Stan LR label style if necessary

    sampler_data = {'x': X, 'y': Y.astype(int), 'd': X.shape[1], 'n': X.shape[0]}

    print('STAN: building/loading model')
    name, code = stan_representation
    sm = build_model(cache_folder, name, code)

    print('STAN: sampling posterior: ' + dnm)
    t0 = time.process_time()
    thd = sampler_data['d']+1
    #call sampling with N_samples actual iterations, and some number of burn iterations
    fit = sm.sampling(data=sampler_data, iter=N_samples*2, chains=chains, control=control, verbose=verbose)
    samples = fit.extract(permuted=False)[:, 0, :thd]
    np.save(os.path.join(cache_folder, dnm+'_samples.npy'), samples) 
    tf = time.process_time()
    np.save(os.path.join(cache_folder, dnm+'_mcmc_time.npy'), tf-t0)
    return samples
