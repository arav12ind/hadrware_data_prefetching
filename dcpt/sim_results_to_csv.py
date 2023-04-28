# %%
import re
import pandas as pd
from collections import defaultdict
import argparse
import pathlib
# %%
parser = argparse.ArgumentParser(
                prog='Champsim Result Prefetcher stats1 Tabulator',
                description="""Takes in multiple ChampSim simulation results files.
                Parses them and stores all the values in csv format.
                Also makes a csv file of prefetch coverage and accuracy""")
parser.add_argument('-y','--overwrite',action='store_true',help="Overwrite output files")
parser.add_argument('-c','--coverage',action='store_true',help="Calculates Prefetcher Coverage and stores in sim_analysis.csv")
parser.add_argument('-a','--accuracy',action='store_true',help="Calculates Prefetcher Accuracy  and stores in sim_analysis.csv")

parser.add_argument('champsim_results',nargs='+',metavar='ChampSim_results',type=pathlib.Path,help="The files with ChampSim simulation output")
parser.add_argument('simdata',type=pathlib.Path,metavar='simdat.csv',help="The csv file in which ChampSim simulation output's stats1 are dumped")
parser.add_argument('sim_analysis',type=pathlib.Path,metavar='sim_analysis.csv',help="The csv file in which prefetcher coverage and and accuracy is written")

speedup_arg=parser.add_argument_group('speedup')
speedup_arg.add_argument('-n','--no-prefetch',nargs='+',metavar='np_prefetch_results',type=pathlib.Path,help="ChampSim simulation output files for no prefetcher system, should have the same name as corresponding ChampSim_results")
speedup_arg.add_argument('-s','--speedup',help="Calculates each speedup using  and stores in sim_analysis.csv. requires -n",action='store_true')
speedup_arg.add_argument('-l','--average-miss-latency',help="Calculates change in average miss latency between no_prefetch_results & ChampSim_results.Stores in sim_analysis.csv. Requires -n",action='store_true')

args = parser.parse_args()
# for arg in vars(args):
#     print(arg, getattr(args, arg))
#%%
exit_flag=0
second_df=args.speedup or args.average_miss_latency
first_df= args.coverage or args.accuracy
if not args.overwrite and args.simdata.exists():
    print(args.simdata," exists")
    exit_flag=-1
if not args.overwrite and args.sim_analysis.exists():
    print(args.sim_analysis," exists")
    exit_flag=-2
if second_df:
    if args.no_prefetch is None:
        print('-s and -l depends on -n option')
        exit_flag=-3
    elif len(args.no_prefetch)!=len(args.champsim_results):
        print('Every no_prefetch_results must be there in champsim_results and viceversa')
        exit_flag=-4
    else:
        np = {x.name for x in args.no_prefetch}
        yp = {x.name for x in args.champsim_results}
        one_side=(np-yp).union(yp-np)
        if len(one_side)>0:
            print('Following files are not in both champsim_results and no_prefetch_results')
            for x in one_side:
                print(x)
            exit_flag=-5
if exit_flag!=0:
    exit(exit_flag)
#%%
def files_to_df(files:list[pathlib.Path]) -> pd.DataFrame:
    stats1=defaultdict(list)
    for chfile in files:
        with open(chfile,'r') as file:
            stats1["name"].append(file.name)
            for line in file:
                # "CPU 0 cumulative IPC: 1.08008 instructions: 500000003 cycles: 462928561"
                m1=re.search(r'^CPU\s*(\d+)\s*cumulative\s*IPC:\s*([0-9.]+)\s*instructions:\s*([0-9]+)\s*cycles:\s*([0-9]+)$',line)
                if m1!=None:
                    cpu_num = f'cpu{str(m1[1])}'.lower()
                    stats1[cpu_num+'_cumulative_ipc'].append(float(m1[2]))
                    stats1[cpu_num+'_instructions'].append(int(m1[3]))
                    stats1[cpu_num+'_cycles'].append(int(m1[3]))
                    continue
                m2=re.search(r'^(\S+) AVERAGE MISS LATENCY: (\S+) cycles$',line)
                if m2!=None:
                    stats1[m2[1].lower() + '_average_miss_latency'].append(float(m2[2]))
                    continue
                m3=re.search(r'^(\S+)\s*([A-Z]+)\s*ACCESS:\s*([0-9]+)\s*HIT:\s*([0-9]+)\s*MISS:\s*([0-9]+)$',line)
                if m3!=None:
                    stat_name = (m3[1] + '_' + m3[2]).lower()
                    stats1[stat_name+'_access'].append(int(m3[3]))
                    stats1[stat_name+'_hit'].append(int(m3[4]))
                    stats1[stat_name+'_miss'].append(int(m3[5]))
                    continue
                m4=re.search(r'^(\S+)\s*([A-Z]+)\s*REQUESTED:\s*([0-9]+)\s*ISSUED:\s*([0-9]+)\s*USEFUL:\s*([0-9]+)\s*USELESS:\s*([0-9]+)$',line)
                if m4!=None:
                    stat_name = (m4[1] + '_' + m4[2]).lower()
                    stats1[stat_name+'_requested'].append(int(m4[3]))
                    stats1[stat_name+'_issued'].append(int(m4[4]))
                    stats1[stat_name+'_useful'].append(int(m4[5]))
                    stats1[stat_name+'_useless'].append(int(m4[6]))
                    continue
    return pd.DataFrame.from_dict(stats1)
df=files_to_df(args.champsim_results)
df.to_csv(args.simdata)
#%%
if first_df or second_df:
    odf=pd.DataFrame()
    odf["name"]=df["name"]
if first_df:
    stats1=defaultdict(list)
    prefetch_re = re.compile(r'^(\S+)prefetch_useful$')
    prefetches=[m.group(1) for m in (prefetch_re.match(clmn) for clmn in df.columns) if m!=None]
    for pfs in prefetches:
        if not (df[pfs+"prefetch_useful"]==0).all():
            if args.coverage:
                odf[pfs+"coverage"]=(df[pfs+"prefetch_useful"]/(df[pfs+"total_miss"]+df[pfs+"prefetch_useful"])*100).round(3)
            if args.accuracy:
                odf[pfs+"accuracy"]=(df[pfs+"prefetch_useful"]/(df[pfs+"prefetch_useful"]+df[pfs+"prefetch_useless"])*100).round(3)

if second_df:
    df2=files_to_df(args.no_prefetch)

    if args.speedup:
        cum_ipc_re = re.compile(r'^(\S+)cumulative_ipc$')
        cumulative_ipcs=[m.group(1) for m in (cum_ipc_re.match(clmn) for clmn in df.columns) if m!=None]
        for cips in cumulative_ipcs:
                odf[cips+"speedup"]=(df[cips+"cumulative_ipc"]/df2[cips+"cumulative_ipc"]).round(4)
    if args.average_miss_latency:
        miss_lat_re = re.compile(r'^(\S+)average_miss_latency$')
        miss_lats=[m.group(1) for m in (miss_lat_re.match(clmn) for clmn in df.columns) if m!=None]
        for mls in miss_lats:
                odf[mls+"relative_latency"]=(df2[mls+"average_miss_latency"]/df[mls+"average_miss_latency"]).round(4)
if first_df or second_df:
    odf.to_csv(args.sim_analysis)