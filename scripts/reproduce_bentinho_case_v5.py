"""Dossiê relatado pelo jogador: duas marcas exclusivas, duas fontes, sem exame."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,UTC
from uuid import UUID,uuid5,NAMESPACE_URL
p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True);args=p.parse_args()
sys.path.insert(0,str(args.source_root.resolve()/'src'))
from memorias_licantropicas.contracts.model import GameState,GameCharacter
from memorias_licantropicas.contracts.investigation import Evidence
from memorias_licantropicas.modules.investigation.catalog import INVENTORIES,ITEMS_BY_ID
from memorias_licantropicas.modules.investigation.rules import make_initial_investigation,make_crime,make_testimony,evaluate_accusation
from memorias_licantropicas.modules.investigation.scoring import assess_dossier
now=datetime(2026,11,4,12,tzinfo=UTC)
game=GameState(id=UUID(int=55445),created_at=now,content_version='3',characters=tuple(GameCharacter(character_id=k,role='werewolf' if k=='bentinho' else 'civil') for k in INVENTORIES))
state=make_initial_investigation(game,now)
common=tuple(i for i in INVENTORIES['bentinho'] if ITEMS_BY_ID[i].kind=='common');singular=next(i for i in INVENTORIES['bentinho'] if ITEMS_BY_ID[i].kind=='singular')
crimes=[]
for day,items in enumerate(((common[0],singular),(common[1],'rosario_seminario'),(common[2],'carta_santiago'),(common[1],'rosario_seminario'),(common[2],'carta_santiago'))):
 crime=make_crime(game,day,'bras_cubas','praca_verde',now)
 evidence=tuple(Evidence(id=uuid5(NAMESPACE_URL,f'bentinho-control:{day}:{item}'),crime_id=crime.id,item_id=item,description=ITEMS_BY_ID[item].description,collected=True,deposited_by='bentinho') for item in items)
 crimes.append(crime.model_copy(update={'evidence':evidence}))
state=state.model_copy(update={'day':5,'crimes':tuple(crimes)})
statements=tuple(make_testimony(state,game,e,person,{i:i for i in INVENTORIES},now) for c in crimes for e in c.evidence for person in ('florenca','bacamarte','bentinho'))
state=state.model_copy(update={'testimonies':statements})
ev=tuple(e.id for c in crimes for e in c.evidence);ts=tuple(t.id for t in statements)
a=assess_dossier(state,'bentinho',ev,ts);decision=evaluate_accusation(state,'bentinho',ev,ts,now)
print(json.dumps({'accepted':a.accepted,'material_points':a.material_points,'total':a.total,'witnesses':sorted(a.independent_witnesses),'examined':sorted(a.examined_exclusive_ids),'route':getattr(a,'custody_route',None),'reason':decision.reason},ensure_ascii=False,indent=2))
