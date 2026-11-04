"""Papel editorial do mestre: compor somente fatos já resolvidos pelo motor."""
from memorias_licantropicas.contracts.investigation import JournalEdition
from memorias_licantropicas.modules.characters.catalog import CHARACTERS
from memorias_licantropicas.modules.characters.language import participle

def word(identifier,masculine,feminine):
 return participle(next((p for p in CHARACTERS if p.id==identifier),None),masculine,feminine)


def final_edition(state, names, *, method=None, werewolf_id=None, detention='none'):
 method=method or state.ending_method
 person=names.get(werewolf_id,werewolf_id or 'a pessoa investigada')
 if state.status=='won':
  headline='Floriano vence: a cidade está livre do lobisomem'
  fact={'detention':f"{person} se transformou na cela, diante da polícia. {person} foi {word(werewolf_id,'expulso','expulsa')} da cidade.",
        'confession':f'{person} admitiu sua participação nos ataques e se entregou ao delegado.',
        'assembly':f"A assembleia confirmou a identidade do lobisomem. {person} foi {word(werewolf_id,'expulso','expulsa')} da cidade."}.get(method,'A investigação confirmou a identidade do lobisomem.')
  body=f'{fact} Floriano encerra o caso. O Clarim do Rio celebra o alívio dos moradores.'
 elif method=='player_expelled':
  headline='Floriano é expulso: a investigação termina sem solução'
  body='A maioria dos moradores expulsou Floriano. O caso termina em derrota do detetive; o perigo permanece.'
 else:
  headline='O Rio perde seus moradores: Floriano não encerrou o caso'
  body='Não restam civis vivos na cidade. Sem identificar e deter o lobisomem a tempo, Floriano perde a investigação.'
 last=state.crimes[-1] if state.status=='lost' and state.crimes and state.crimes[-1].day==state.day-1 else None
 return JournalEdition(victim_id=last.victim_id if last else None,location_id=last.location_id if last else None,day=state.day,illustration='victory' if state.status=='won' else 'crime_street',
                       headline=headline,body=body,suspicious_death_count=len(state.crimes),detention_outcome=detention)


def morning_edition(day,crimes,new_crimes,names,detention='none',detainee_id=None):
 count=len(crimes)
 if new_crimes:
  people=' e '.join(names.get(c.victim_id,c.victim_id) for c in new_crimes)
  headline=f'Já são {count} mortes suspeitas: a cidade exige respostas'
  body=f'{people}: a manhã revelou {len(new_crimes)} nova'+(' morte suspeita.' if len(new_crimes)==1 else 's mortes suspeitas.')
  body+=' A autoria de cada crime ainda é investigada. Floriano compara as cenas, os vestígios e as versões dos moradores.'
  primary=new_crimes[0];location=primary.location_id;victim=primary.victim_id
 else:
  headline=f'Sem nova vítima; {count} mortes suspeitas seguem sob investigação'
  body='A cidade amanhece sem nova morte. Uma noite de silêncio não encerra o caso; Floriano prossegue com a investigação.'
  victim=None;location=None
 if detainee_id and detention=='released':
  body+=f" {names.get(detainee_id,detainee_id)} não se transformou e foi {word(detainee_id,'solto','solta')} pela manhã."
 illustration='quiet' if not location else 'crime_docks' if location=='cais_lanternas' else 'crime_garden' if location in {'casa_verde','cabana_capitu'} else 'crime_street'
 return JournalEdition(day=day,headline=headline,body=body,illustration=illustration,victim_id=victim,
                       location_id=location,suspicious_death_count=count,detention_outcome=detention)
