# -*- coding: utf-8 -*-
"""
Created on Sat Mar 12 08:11:13 2022

@author: Ken
"""

import os
from time import time
import pandas  as pd
import numpy as np
from dash import html, dcc
import dash_bootstrap_components as dbc  # Allows easy access to all bootstrap themes
import datetime as dt

in_spyder   = str(os.environ).count('SPY_') > 10
in_jupyter  = str(os.environ).count('SPY_') < 10 and  str(os.environ).count('JPY_') > 1
in_gunicorn = str(os.environ).count('gunicorn') > 0

brand_div = html.Div([
            html.Img(src='/assets/First_Analytics_logo_rgb no background.png',style={'height':'15%', 'width':'15%'}),
            html.Br(),
            html.Br(),            
            ], style={'margin-left':'10px','margin-top':'5px'}
            )

# def logit(*args, sep=' ', end='\n', file=None):
#     '''Write a message to the log.'''
#     print(f"[{dt.now().strftime('%Y%m%d_%H%M%S.%f')[:19]}]", *args)
    

def logit(*args):
    text = ' '.join(map(str,args))
    for txt in text.split('\n'):
        print(f"[{dt.datetime.now(dt.UTC).strftime('%Y%m%d_%H%M%S.%f')}] {txt}", *args)  # kma 20250516 changed to log multiple lines, with UTC
        
    
def instantiate_app(app_title='title', external_stylesheets=[], **kwargs):  # returns a Dash app
    flask_server = None
    assets_folder=os.path.join(os.getcwd(),'assets')
    logit(f'{assets_folder=}')
    if in_gunicorn:
        import flask
        from dash import Dash
        flask_server = flask.Flask(__name__) # define flask app.server
        logit(f'Instantiating Dash for gunicorn with {assets_folder=}')
        logit(f'{external_stylesheets=}')
        app = Dash(__name__, server=flask_server, title=app_title, 
                    external_stylesheets=external_stylesheets,
                    assets_folder=assets_folder,
                    **kwargs)
    elif in_jupyter:
        logit(f'Instantiating JupyterDash with {assets_folder=}')
        logit(f'{external_stylesheets=}')
        from jupyter_dash import JupyterDash  # Needed to run in Jupyter notebook
        app = JupyterDash(__name__ , title=app_title, external_stylesheets=external_stylesheets)  
    else:
        from dash import Dash
        # app = Dash(__name__ , title=app_title, external_stylesheets=external_stylesheets)
        logit(f'Instantiating Dash with {assets_folder=}')
        logit(f'{external_stylesheets=}')
        app = Dash(__name__ , title=app_title, 
                   external_stylesheets=external_stylesheets, 
                   assets_folder=assets_folder,
                   **kwargs)
    return flask_server, app

def get_open_port(beg=8050,end=8299):
    from psutil import net_connections
    addr_inuse = [[conn.raddr, conn.laddr] for conn in net_connections()]
    ports = set(addr.port for addr in sum(addr_inuse, []) if addr)
    for use_port in range(beg, end):
        if use_port not in ports: 
            break  
    return use_port


def run_server(app, use_port=8050, debug=None):    
    os.environ["DASH_HOT_RELOAD_INTERVAL"] = "9000"
    if debug is None:
        logit(f'setting debug to {not in_gunicorn}')
        debug = not in_gunicorn
    if in_jupyter:
        mode = 'external'
        logit(f'Starting server on http://localhost:{use_port}/ with mode="{mode}" and debug={debug}')
        app.run_server(mode=mode, debug=debug, port=use_port)
    else:
        logit(f'Starting server on http://localhost:{use_port}/ with no mode specified and debug={debug}')
        app.run_server(debug=debug, port=use_port)


def get_data(filename_or_relative_path, sheet_name=None, folder='data'):    
    timeBeg = time()  # to time how long it takes
    fileNameBase, fileNameExt = os.path.splitext(filename_or_relative_path)
    if fileNameExt in '.xls .xlsx':
        datapath = os.path.join(os.getcwd(), folder, filename_or_relative_path)
        logit(f'get_data: reading excel sheet "{sheet_name}" from {datapath}')
        df = pd.read_excel(open(datapath, 'rb'), sheet_name=sheet_name)
        logit(f'get_data: loaded "{filename_or_relative_path}" in {1000*(time()-timeBeg):.3f} ms')
        return df
    else:
        msg = f'Not Implemented:  reading from files with extension {fileNameExt}'
        logit(msg)
        # maybe should thow and error
        return None
    
def make_dropdown_item(ddt_row, df):
    ddr0 = [
        html.H6(ddt_row.heading),
        dcc.Dropdown(
            options = np.append(np.array(ddt_row.opt), np.sort(df[ddt_row.df_column].unique())),
            multi = ddt_row.multi=='True',  # Allow multiple selections
            value = ddt_row.value,
            style={'width':ddt_row.width},
            id=ddt_row.id
            )
        ]
    return ddr0

def make_dropdowns(dropdown_tbl, df):
    from addict import Dict
    ddt = []
    keys = [k.strip() for k in dropdown_tbl[0].split('|')]
    for row in dropdown_tbl[1:]:
        values = [k.strip() for k in row.split('|')]
        ddt.append(Dict(zip(keys,values)))
    return [dbc.Col(make_dropdown_item(row, df)) for row in ddt]