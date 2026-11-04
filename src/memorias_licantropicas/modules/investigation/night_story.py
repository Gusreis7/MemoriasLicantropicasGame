"""Duas causas de morte independentes; sorteios privados estáveis por noite."""
from hashlib import sha256
from secrets import choice, token_hex
from memorias_licantropicas.contracts.investigation import NightStory, MurderPlot

WEREWOLF_ATTACK_CHANCE=.65

def make_night_story(game):
 civils=tuple(m.character_id for m in game.characters if m.role=='civil' and m.alive)
 plot=None
 if len(civils)>=2:
  actor=choice(civils);target=choice(tuple(p for p in civils if p!=actor))
  plot=MurderPlot(planner_id=actor,target_id=target)
 return NightStory(seed=token_hex(24),plot=plot)

def roll(story,night,channel):
 return int.from_bytes(sha256(f'{story.seed}:{night}:{channel}'.encode()).digest()[:8],'big')/2**64

def civil_probability(night):
 return .25 * (2.0 ** -min(max(0,night-1),1024))

def resolve_story(state,game,choose_victim):
 """Retorna (história, ataques). O lobo age primeiro; a polícia impede ações do preso."""
 story=state.night_story or make_night_story(game)
 blocked={*state.expelled_npc_ids,state.detained_npc_id}
 alive={m.character_id for m in game.characters if m.alive}
 wolf=next(m.character_id for m in game.characters if m.role=='werewolf')
 attacks=[]
 candidate=choose_victim(game,detained_npc_id=state.detained_npc_id,excluded_ids=state.expelled_npc_ids)
 if wolf not in blocked and candidate and (story.skipped_nights>=1 or roll(story,state.day,'werewolf')<WEREWOLF_ATTACK_CHANCE):
  attacks.append((wolf,candidate,'werewolf'));alive.discard(candidate)
  story=story.model_copy(update={'skipped_nights':0})
 elif wolf not in blocked:
  story=story.model_copy(update={'skipped_nights':min(1,story.skipped_nights+1)})
 plot=story.plot
 if plot and plot.status=='planning':
  if plot.target_id not in alive:
   plot=plot.model_copy(update={'status':'frustrated','stress':90})
  elif plot.planner_id not in alive or plot.planner_id in state.expelled_npc_ids:
   plot=plot.model_copy(update={'status':'interrupted'})
  elif plot.planner_id not in blocked and plot.target_id not in blocked:
   success=roll(story,state.day,'civil')<civil_probability(state.day)
   plot=plot.model_copy(update={'attempts':plot.attempts+1,'stress':min(100,plot.stress+10),
                               'status':'succeeded' if success else 'planning'})
   if success: attacks.append((plot.planner_id,plot.target_id,'civil'))
  story=story.model_copy(update={'plot':plot})
 return story,tuple(attacks)


def plot_context(state,npc_id,names):
 plot=state.night_story.plot if state.night_story else None
 if not plot or plot.planner_id!=npc_id:return None
 return {'alvo':names.get(plot.target_id,plot.target_id),'estado':plot.status,'estresse':plot.stress,
         'intencao':('Você planejou matar essa pessoa por um conflito pessoal. Isso não faz de você o lobisomem.'),
         'lembranca':('O alvo morreu antes de sua tentativa; você está frustrado e estressado.' if plot.status=='frustrated' else
                     'Você cometeu esse homicídio, separadamente dos ataques da fera.' if plot.status=='succeeded' else
                     'O plano não foi consumado.'),
         'regra':'Interprete seu conflito sem revelar campos internos. Pode negá-lo ou admiti-lo na conversa; a fala não executa ações.'}
