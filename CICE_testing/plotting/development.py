"""PyGMT conceptual case diagrams; never presented as observed CICE output."""
import argparse
import csv
import io
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import numpy as np


class DevelopmentFigures:
    def __init__(self, output):
        self.output=Path(output)
        self.cases=json.loads(files('CICE_testing.resources').joinpath('development_cases.json').read_text())

    @staticmethod
    def rectangle(fig,x0,x1,y0,y1,color,pen='0.5p,white'):
        fig.plot(x=[x0,x1,x1,x0,x0],y=[y0,y0,y1,y1,y0],fill=color,pen=pen,close=True)

    def grid(self, fig, band=(), tensile=True, title='Prescribed box', coefficient=True):
        fig.basemap(region=[.5,12.5,.5,12.5],projection='X11c/9c',
                    frame=['xa2f1+lGlobal column i','ya2f1+lGlobal row j','+t'+title])
        for j in range(1,13):
            for i in range(1,13):
                ocean=3<=i<=10 and 3<=j<=10
                color='#D9D9D9' if not ocean else '#F2B880' if i in band else '#B5DDE2'
                self.rectangle(fig,i-.5,i+.5,j-.5,j+.5,color)
        fig.plot(x=[6.5,6.5],y=[.5,12.5],pen='1.5p,#6B4C9A,--')
        for i in (4,5,8,9):
            direction=-1 if tensile and i<=6 else 1
            fig.plot(x=[i],y=[8.5],direction=[[0 if direction>0 else 180],[.6]],
                     style='v0.2c+e',pen='1.3p,#333333',fill='#333333')
        fig.text(x=6.5,y=11.6,text='Land boundary',font='9p')
        fig.text(x=6.5,y=1.4,text='64 ocean cells; 16 km spacing',font='9p')
        fig.text(x=6.5,y=6.2,text='i=6/7 block interface',font='9p',fill='white')
        if coefficient:
            fig.text(x=6.5,y=3.5,text='Orange: g=0.5; blue: g=1',font='9p',fill='white')

    def timeline(self,fig,case):
        fig.basemap(region=[0,120,0,4],projection='X15c/7c',
                    frame=['xa24f12+lModel hours from 1 January','y','+t'+case+': continuous and split paths'])
        self.rectangle(fig,0,120,2.7,3.3,'#B5DDE2')
        self.rectangle(fig,0,48,1.2,1.8,'#B5DDE2')
        self.rectangle(fig,48,120,1.2,1.8,'#F2B880')
        fig.text(x=60,y=3,text='Continuous: 5 days',font='11p')
        fig.text(x=24,y=1.5,text='Initial: 2 days',font='11p')
        fig.text(x=84,y=1.5,text='Continue: 3 days',font='11p')
        fig.plot(x=[48,48],y=[.8,3.6],pen='1p,#6B4C9A,--')
        fig.text(x=48,y=.55,text='Restart: step 48; independent IC check',font='10p')
        fig.text(x=60,y=3.8,text='Expected: exact phase-aligned trajectories',font='10p')

    def mapping(self,fig,case):
        f=np.linspace(0,1,101)
        fig.basemap(region=[0,1,0,1.12],projection='X14c/8c',
                    frame=['xaf+lLarge-floe ice-area fraction','yaf+lDimensionless coefficient','+t'+case+': analytical mapping'])
        fig.plot(x=f,y=.2+.8*f,pen='2p,#007C91',label='g candidate')
        fig.plot(x=f,y=.2*(.2+.8*f),pen='2p,#D2691E',label='Ktens candidate')
        fig.plot(x=[0,.5,2/3,1],y=[.2,.6,11/15,1],style='c0.18c',fill='#007C91')
        fig.legend(position='JTL+jTL+o0.2c',box='+gwhite+p0.4p')

    def logic(self,fig,case):
        descriptions={
          'B6.3':[('Live FSD','After restoration / pre-EVP'),('Candidate g','Diagnosed; no momentum input'),('Applied g=1','Physical control must match')],
          'B6.6':[('Valid occupied FSD','Status 0; bounded candidate'),('A <= 1e-12','Status 1; fraction masked'),('Invalid occupied FSD','Status 6; collective abort')],
          'G0':[('Inherited forcing','ERA5 / ORAS / waves'),('Off versus unity','Common executable / inputs'),('Mechanical + thermal','State, fluxes, restart / layout')],
          'G1':[('Evolving global FSD','Raw bins / category areas'),('Candidate diagnosed','Invalid-state policy explicit'),('Momentum unchanged','Physical / thermal control')],
          'G2':[('Valid feedback input','G0 and G1 prerequisites'),('Mechanical response','Stress, deformation, transport'),('Thermal budgets','Growth / melt / ocean fluxes')],
          'B6.5-F':[('Shadow mapped g','Small / mixed / large'),('Independent constant g','0.2 / 0.6000000000000001 / 1'),('Exact equivalent paths','History / restart / layouts')],
        }
        rows=descriptions[case]
        fig.basemap(region=[0,10,0,7],projection='X15c/9c',frame=['+t'+case+': conceptual acceptance design'])
        for index,(label,detail) in enumerate(rows):
            y=5.6-index*2
            self.rectangle(fig,.5,9.5,y-.6,y+.6,['#B5DDE2','#F2B880','#DDD1EC'][index],pen='1p,#444444')
            fig.text(x=5,y=y+.18,text=label,font='13p,Helvetica-Bold')
            fig.text(x=5,y=y-.25,text=detail,font='10p')
        # These are alternative validation branches for B6.6, not sequential states.
        if case!='B6.6':
            for y in (4.9,2.9):
                fig.plot(x=[5],y=[y],direction=[[-90],[.45]],pen='1p,#444444',style='v0.15c+e',fill='#444444')

    def concept(self,case,band=None):
        if case not in self.cases['titles']: raise ValueError('unknown development case')
        import pygmt
        fig=pygmt.Figure()
        with pygmt.config(FONT_TITLE='13p',FONT_LABEL='10p',FONT_ANNOT_PRIMARY='9p',MAP_FRAME_TYPE='plain'):
            if case in ('B0','B1','B3'):
                self.grid(fig,band=(band or (6,7)) if case=='B3' else (),tensile=case=='B3',
                          title=case+': '+('zero tensile baseline' if case=='B0' else 'unity identity' if case=='B1' else 'prescribed weak band '+('6 only' if band==(6,) else '6-7')),coefficient=case=='B3')
            elif case in ('B5','B6.4'):self.timeline(fig,case)
            elif case in ('B6','B6.2','B6.5'):self.mapping(fig,case)
            elif case=='B6.1':
                diam=np.array([5.376808,19.596895,43.344255,81.469882,140.281354,227.387610,351.154222,519.673026,739.240333,1012.480284,1336.418272,1700.953881])
                fig.basemap(region=[.5,12.5,0,1850],projection='X14c/8c',frame=['xa1+lNative floe bin','ya500f100+lRepresentative diameter (m)','+tB6.1: radius-centre to diameter audit'])
                for i,d in enumerate(diam,1):fig.plot(x=[i],y=[d],style='b0.5c',fill='#007C91' if d<=300 else '#D2691E')
                fig.plot(x=[.5,12.5],y=[300,300],pen='1p,#6B4C9A,--')
                fig.text(x=8,y=160,text='Strict D > 300 m; whole-bin classification',font='9p')
            elif case in ('B2','B4'):
                labels=['Enabled: 0.2 x 0.5','Disabled: 0.1'] if case=='B2' else ['off','unity','spatial null','half']
                effective=[.1,.1] if case=='B2' else [.2,.2,.2,.1]
                fig.basemap(region=[-.5,len(labels)-.5,0,.26],projection='X14c/8c',frame=['x','ya.05+lEffective tensile coefficient','+t'+case+': expected coefficient equivalence'])
                fig.plot(x=range(len(labels)),y=effective,style='b1c',fill='#007C91')
                for i,label in enumerate(labels):fig.text(x=i,y=.235,text=label,font='10p')
            else:self.logic(fig,case)
        scope='global' if case.startswith('G') else 'box'
        target=self.output/scope;target.mkdir(parents=True,exist_ok=True)
        stem=case+('_band6' if case=='B3' and band==(6,) else '')
        outputs=[]
        for ext in ('png','pdf'):
            p=target/(stem+'.'+ext);fig.savefig(str(p),dpi=180);outputs.append(p)
        record=dict(case=case,kind='conceptual design / analytical expectation',backend='PyGMT',
                    measured_model_data=False,band=band,gate_status=self.cases['status'][case],
                    code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs})
        (target/(stem+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        return fig



    def reported(self,case):
        """Plot only snapshot values explicitly recorded in the stage documents."""
        import pygmt
        raw=files('CICE_testing.resources').joinpath('box_reported_snapshots.csv').read_text()
        rows=[r for r in csv.DictReader(io.StringIO(raw)) if r['case']==case]
        if not rows:raise ValueError('no reported numerical snapshots for '+case)
        fig=pygmt.Figure()
        panels=sorted({int(r['hour']) for r in rows}) if case in ('B3','B4') else [None]
        with fig.subplot(nrows=1,ncols=len(panels),figsize=(14*len(panels),8),margins='0.6c'):
            for panel,hour in enumerate(panels):
                subset=[r for r in rows if hour is None or int(r['hour'])==hour]
                low=min(float(r['minimum']) for r in subset);high=max(float(r['maximum']) for r in subset)
                pad=max((high-low)*.15,abs(high)*.1,1e-3)
                with fig.set_panel(panel=panel):
                    fig.basemap(region=[-.5,len(subset)-.5,low-pad,high+pad],projection='X?',
                        frame=['x','yaf+l'+subset[0]['field']+' ('+subset[0]['units']+')',
                               '+t'+case+': reported snapshots'+(' hour '+str(hour) if hour else '')])
                    for index,row in enumerate(subset):
                        y0,y1=float(row['minimum']),float(row['maximum'])
                        fig.plot(x=[index,index],y=[y0,y1],pen='2p,#007C91')
                        fig.plot(x=[index,index],y=[y0,y1],style='c0.13c',fill='#007C91')
                        label=row['label'] if hour else 'hour '+row['hour']
                        fig.text(x=index,y=high+pad*.5,text=label,font='10p')
        destination=self.output/'box';destination.mkdir(parents=True,exist_ok=True)
        stem=case+'_reported';outputs=[]
        for ext in ('png','pdf'):
            p=destination/(stem+'.'+ext);fig.savefig(str(p),dpi=180);outputs.append(p)
        record=dict(case=case,backend='PyGMT',kind='user-reported snapshot values transcribed from stage records',
                    raw_NetCDF_inspected=False,source_csv_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                    notes='Bars show reported spatial minima/maxima, not confidence intervals. B3 C used a different executable; retain that attribution limit.',
                    outputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs})
        (destination/(stem+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        return fig

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',default='all')
    args=p.parse_args();work=DevelopmentFigures(args.output)
    for case in work.cases['titles'] if args.case=='all' else [args.case]:
        work.concept(case)
        if case=='B3':work.concept(case,band=(6,))
        if case in ('B0','B3','B4','B5'):work.reported(case)

if __name__=='__main__':main()
