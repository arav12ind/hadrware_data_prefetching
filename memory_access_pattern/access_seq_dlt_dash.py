import struct
from numpy.random import choice
from io import BufferedReader
from typing import Tuple

import dash
import itertools
from dash import html
from dash import dcc
from dash.dependencies import Input, Output,State
from dash.long_callback import DiskcacheLongCallbackManager

import plotly.express as px
from plotly.graph_objects import Figure
import lzma
from collections import defaultdict as dd
import os

import pandas as pd
import numpy as np
import diskcache


cache = diskcache.Cache("./cache")
long_callback_manager = DiskcacheLongCallbackManager(cache)

## * Initialize dash app
app = dash.Dash(__name__, long_callback_manager=long_callback_manager)

_file_name=""
_acc_no=0
_num_accs=1024
_sample_chance=100
_access = dd(int)
_ips=[]
"""
@param trace_file is a seekable file, open for reading in binary mode.
@param acc_no is the record in the file from which to start the data reading.
@param num_accs is the number of records to iterate through, does not represent the number of data points that will pe returned.
@param sample_chance is the sampling probability for the records.
* Returns delta sequence of cache line numbers for each IP.
* Delta sequence is the difference between consecutive accesses.
"""
def get_access_dlt_seq(trace_file: BufferedReader,acc_no:int,num_accs:int,sample_chance:int) -> Tuple[dd[str, list],list[str]]:
    acc_seq_struct='<2Q'
    rec_len=struct.calcsize(acc_seq_struct)
    blk_bits=6
    access_seq = dd(list)
    trace_file.seek(acc_no*rec_len)
    line_count,last_accs=acc_no,acc_no+num_accs
    prob=sample_chance/100
    probability_tf=[prob,1-prob]
    ## * last_acc maps the IP to the last access address related to it.
    last_acc = dd(int)
    while (ln := trace_file.read(rec_len)) and line_count<last_accs:
        if choice([True,False],1,p=probability_tf):
            ip,acc=struct.unpack(acc_seq_struct,ln)
            acc=acc>>blk_bits
            if ip in last_acc:
                access_seq['Access No'].append(line_count)
                access_seq['IP'].append(ip)        
                access_seq['Cache Line Delta'].append(acc-last_acc[ip])
            last_acc[ip]=acc
            line_count+=1
    return access_seq,[hex(x)[2:].upper() for x in last_acc.keys()]


@app.long_callback(Output(component_id='ip_graph',component_property='figure'),
              inputs=dict(
                            ip=Input(component_id='ips',component_property='value')
                        ),
              state=dict(
                            fig3d=State(component_id='3d_scatter',component_property='figure')
              ),
              running=[(Output(component_id='refresh_btn',component_property='disabled'),True,False),
                       (Output(component_id='ips',component_property='disabled'),True,False)],
              prevent_initial_call=True
              )
def get_ip(ip:str,fig3d:Figure):
    data=fig3d["data"][0]
    df=pd.DataFrame(list(zip(data["x"],data["y"],data["z"])),columns=['Access No','IP','Cache Line Delta'])
    df_ip=df[df['IP']==int(ip,16)]
    fig = px.scatter(df_ip,x='Access No',y='Cache Line Delta',title=f'IP={ip}')
    fig.update_layout(
        scene=dict(
            xaxis={},
            yaxis=dict(tickformat='x'),
            ),
            uirevision='0',
            # template='plotly_dark'
        )
    return fig

"""
* Tells Dash app to call the function below (get_fig) when there is a change in the value of any item in inputs.
* This is associated with app.layout that comes later in the code.
"""
@app.long_callback(Output(component_id='3d_scatter',component_property='figure'),
                   Output(component_id='ips',component_property='options'),
                   Output(component_id='access_graph',component_property='figure'),
              inputs=dict(
                            n_clicks=Input(component_id='refresh_btn',component_property='n_clicks')
                        ),
              state=dict(
                        fig=State(component_id='3d_scatter',component_property='figure'),
                        acc_gf=State(component_id='3d_scatter',component_property='figure'),
                        file_name=State(component_id='traces',component_property='value'),
                        acc_no=State(component_id='acc_no',component_property='value'),
                        num_accs=State(component_id='num_accs',component_property='value'),
                        sample_chance=State(component_id='sample_chance',component_property='value')
                    ),
              running=[(Output(component_id='refresh_btn',component_property='disabled'),True,False),
                       (Output(component_id='ips',component_property='disabled'),True,False)]
              )
def get_fig(fig:Figure,acc_gf:Figure,file_name:str,acc_no:int,num_accs:int,sample_chance:int,n_clicks:int) -> Figure:
    global _file_name
    global _acc_no
    global _num_accs
    global _sample_chance
    global _access
    global _ips
    if (
        _file_name == file_name
        and _acc_no == acc_no
        and _num_accs == num_accs
        and _sample_chance == sample_chance
    ):
        print('No change')
        return fig,_ips,acc_gf
    with lzma.open(f"ipas/{file_name}.ipas.xz") as trace_file:
        access_lst,ips=get_access_dlt_seq(trace_file,acc_no,num_accs,sample_chance)
        ips.sort()
        _ips=ips
        fig = px.scatter_3d(access_lst,x='Access No',y='IP',z='Cache Line Delta')
        #,z='Cache Line Delta',color=px.Constant('chartreuse'),color_discrete_map="identity"
        fig.update_layout(
            scene=dict(
                xaxis={},
                yaxis=dict(tickformat='x'),
                zaxis=dict( tickformat='x')
                ),
                uirevision='0',
                # template='plotly_dark'
            )
        fig.update_traces(marker=dict(size=1))

        acc_gf = px.line(access_lst,x='Access No',y='IP',markers='.')
        acc_gf.update_layout(
                yaxis_tickformat = 'x',
                uirevision='0',
                # template='plotly_dark'
            )
    _file_name=file_name
    _acc_no=acc_no
    _num_accs=num_accs
    _sample_chance=sample_chance
    _access=pd.DataFrame(access_lst)
    return fig,ips,acc_gf

# * Gets all the compressed access sequence files from the ipas directory and they must end with extension .ipas.xz.
traces=[file[:-8] for file in os.listdir('ipas') if file.endswith('.ipas.xz')]
traces.sort()
"""
* Designs the app looks.
"""
label_style={"margin-left": "25px",'font-weight': 'bold', "text-align": "right","margin-right": "10px"}

app.layout = html.Div(id = 'parent', children = [
    # * Dropdown menu for choosing the trace file.
    html.Div(id='dropdowns',style=dict(display="flex"),
             children=[html.Div(id='dropdown-1',children=[dcc.Dropdown(traces,value=traces[0],id='traces',clearable=False)],style={'width':"50%"}),
    html.Div(id='dropdown-2',children=[dcc.Dropdown(id='ips',clearable=False,placeholder='IP')],style={'width':"50%"})]),
    # * Other parameters
    html.Div([
    # * The records number to start from.
    html.Label(["First Access No."],style=label_style),
    dcc.Input(id='acc_no',type='number',placeholder="first access no.",value=0, debounce=True),

    # * Number of records to consider.
    html.Label(["No. Of Accesses"],style=label_style),
    dcc.Input(id='num_accs',type='number',placeholder="No of access",value=1024, debounce=True),

    # * Sampling probability in percentage.
    html.Label(["Sample Chance"],style=label_style),
    dcc.Input(id='sample_chance',type='number',placeholder="Sample Chance",value=100,min=0,max=100, debounce=True),

    # * Button to apply the above parameters.
    html.Button('Refresh',id='refresh_btn'),

    # * The 3D graph
    dcc.Graph(id = '3d_scatter',style={'width': '100wh', 'height': '90vh','align':'centre'}),
    dcc.Graph(id='access_graph',style=dict(align='center')),
    dcc.Graph(id='ip_graph',style=dict(align='center')),
    ])
])
    
if __name__ == '__main__':
    app.run_server(host= '0.0.0.0',debug=False)