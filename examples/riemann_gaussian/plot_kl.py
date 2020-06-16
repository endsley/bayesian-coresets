import bokeh.plotting as bkp
from bokeh.io import export_png, export_svgs
import numpy as np
import sys, os
import argparse
#make it so we can import models/etc from parent folder
sys.path.insert(1, os.path.join(sys.path[0], '../common'))
from plotting import *

parser = argparse.ArgumentParser(description="Plots Riemannian linear regression experiments")
parser.add_argument('n_trials', type=int, help="This script will look for & plot experiments with trial IDs 1 through n_trials (inclusive)")
parser.add_argument('names', type = str, nargs = '+', default = ["SVI", "RAND", "GIGAO", "GIGAR"], help = "a list of which algorithm names to plot results for (Examples: SVI / GIGAO / GIGAR / RAND)")
parser.add_argument('--fldr', type=str, default="results/", help="This script will look for & plot experiments in this folder")
parser.add_argument('--plot_every', type=int, default='1', help="Coarseness of the graph - will skip (plot_every-1) points between each plotted point")
parser.add_argument('--d', type=int, default = '200', help="The dimension of the multivariate normal distribution used for these experiments")
parser.add_argument('--M', type=int, default='200', help='The desired maximum coreset size specified for these experiments')
parser.add_argument('--N', type=int, default='1000', help='Dataset size/number of examples for these experiments')
parser.add_argument('--proj_dim', type=int, default = '100', help = "The number of samples taken when discretizing log likelihoods for these experiments")
parser.add_argument('--SVI_opt_itrs', type=int, default = '500', help = '(If using SVI/HOPS) The number of iterations used when optimizing weights.')
parser.add_argument('--fwd', action='store_const', const=True, default = False, help = 'If this flag is provided, will plot forward KL divergence instead of reverse KL divergence')


arguments = parser.parse_args()
n_trials = arguments.n_trials
names = arguments.names
fldr = arguments.fldr
plot_every = arguments.plot_every
M = arguments.M
N = arguments.N
d = arguments.d
proj_dim = arguments.proj_dim
SVI_opt_itrs =  arguments.SVI_opt_itrs

algs = {'SVIEXACT': 'Sparse VI (Exact Tangent Space)',
        'SVI': 'Sparse VI', 
        'GIGAO': 'GIGA(Optimal)', 
        'GIGAR': "GIGA(Realistic)", 
        'RAND': "Uniform", 
        'HOPS': "HOPS",
        'HOPSEXACT': "HOPS (Exact Tangent Space)"}
nms = []
for name in names:
  nms.append((name, algs[name]))

plot_reverse_kl = not arguments.fwd
trials = np.arange(1, n_trials + 1)

#plot the KL figure
fig = bkp.figure(y_axis_type='log', plot_width=850, plot_height=850, x_axis_label='Coreset Size',
       y_axis_label=('Reverse KL' if plot_reverse_kl else 'Forward KL'), toolbar_location=None )
preprocess_plot(fig, '32pt', False, True)

for i, nm in enumerate(nms):
  kl = []
  sz = []
  for tr in trials:
    numTuple = (nm[0], str(d), str(tr), str(N), str(proj_dim), str(SVI_opt_itrs))
    print(os.path.join(fldr, '_'.join(numTuple)+'.pk'))
    x_, mu0_, Sig0_, Sig_, mup_, Sigp_, w_, p_, muw_, Sigw_, rklw_, fklw_ = np.load(os.path.join(fldr, '_'.join(numTuple)+'.pk'), allow_pickle=True)
    if plot_reverse_kl:
      kl.append(rklw_[::plot_every])
    else:
      kl.append(fklw_[::plot_every])
      
    sz.append([np.count_nonzero(a) for a in w_[::plot_every]])

  x = np.percentile(sz, 50, axis=0)
  fig.line(x, np.percentile(kl, 50, axis=0), color=pal[i-1], line_width=5, legend=nm[1])
  fig.patch(x = np.hstack((x, x[::-1])), y = np.hstack((np.percentile(kl, 75, axis=0), np.percentile(kl, 25, axis=0)[::-1])), color=pal[i-1], fill_alpha=0.4, legend=nm[1])

postprocess_plot(fig, '20pt', location='bottom_right', glyph_width=40)
fig.legend.background_fill_alpha=0.
fig.legend.border_line_alpha=0.
fig.legend.visible = True

bkp.show(fig)
#fig.output_backend = "svg"
#fldr_figs = 'figs'
#if not os.path.exists(fldr_figs):
#  os.mkdir(fldr_figs)
#export_png(fig, filename=os.path.join(fldr_figs, "d"+str(d)+"_KLDvsCstSize.png"), height=1500, width=1500)
