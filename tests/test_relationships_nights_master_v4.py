from datetime import UTC,datetime,timedelta
from uuid import uuid4
from collections import Counter
import pytest
from test_interrogations import inquiry
from src.contracts.model import GameState,GameCharacter,ConversationMessage
from src.contracts.social import SocialState
from src.contracts.investigation import NightStory,MurderPlot
from src.modules.knowledge.affects import IDS,MATRIX,initial_affects
from src.modules.knowledge.rules import initial_relationships
from src.modules.knowledge.seeds import seed_social_state
from src.modules.investigation.rules import make_initial_investigation,choose_victim,make_crime
from src.modules.investigation.night_story import resolve_story,civil_probability,plot_context
from src.modules.session_master.service import local_assessment
from src.modules.session_master.rules import dialogue_transition
from src.modules.session_master.reports import useful_report
from src.modules.session_master.editorial import final_edition
from src.modules.agents.support import compact_observations
from src.modules.conversations.service import public_message

NOW=datetime(2026,11,4,12,tzinfo=UTC)

def cast():
 return GameState(id=uuid4(),created_at=NOW,content_version='3',characters=tuple(
  GameCharacter(character_id=p,role='werewolf' if p=='bentinho' else 'civil') for p in IDS[:-1]))

def scenario():
 game=cast();state=make_initial_investigation(game,NOW)
 return game,state.model_copy(update={'night_story':NightStory(seed='fixed',plot=MurderPlot(planner_id='rubiao',target_id='florenca'))})

def test_all_64_directional_feelings_and_self_relations_are_present():
 relations={(r.actor_id,r.target_id):r for r in initial_affects(IDS[:-1])}
 for actor,row in MATRIX.items():
  for target,label in zip(IDS,row):
   assert relations[actor,target].sentiment_label==label
   assert relations[actor,target].sentiments
 assert relations['bentinho','capitu'].sentiments['amor']>0
 assert relations['bentinho','capitu'].sentiments['ódio']>0
 assert relations['escobar','bentinho'].sentiments!=relations['bentinho','escobar'].sentiments
 assert relations['florenca','bacamarte'].sentiment_label=='apatia'

def test_topic_initialization_preserves_current_relationship_changes():
 game=cast();current=initial_relationships(IDS[:-1]);cause=uuid4()
 current=tuple(r.model_copy(update={'trust':r.trust+3,'causes':(cause,)}) if (r.actor_id,r.target_id)==('bentinho','capitu') else r for r in current)
 state=SocialState(game_id=game.id,relationships=current)
 initialized=seed_social_state(state,IDS[:-1],NOW)
 assert initialized.relationships==current
 assert initialized.topics_initialized
 assert seed_social_state(initialized,IDS[:-1],NOW)==initialized

@pytest.mark.parametrize('night,p',[(1,.25),(2,.125),(3,.0625),(4,.03125)])
def test_plot_chance_halves_by_calendar_night(night,p):assert civil_probability(night)==p

def test_civil_plot_is_a_living_civil_pair_never_wolf_self_or_bras():
 for _ in range(100):
  game=cast();state=make_initial_investigation(game,NOW);plot=state.night_story.plot
  assert plot and plot.planner_id!=plot.target_id
  assert {plot.planner_id,plot.target_id}<=set(IDS[1:-1])

def test_wolf_cannot_skip_two_nights_even_when_civil_kills(monkeypatch):
 game,state=scenario()
 monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda s,n,c: .99 if c=='werewolf' else 0.)
 story,attacks=resolve_story(state,game,choose_victim)
 assert [cause for _,_,cause in attacks]==['civil'] and story.skipped_nights==1
 story,attacks=resolve_story(state.model_copy(update={'day':2,'night_story':story}),game,choose_victim)
 assert any(cause=='werewolf' for _,_,cause in attacks) and story.skipped_nights==0

def test_wolf_killing_target_frustrates_plot_and_no_second_murder(monkeypatch):
 game,state=scenario()
 monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a:0.)
 story,attacks=resolve_story(state,game,lambda *a,**k:'florenca')
 assert attacks==(('bentinho','florenca','werewolf'),)
 assert story.plot.status=='frustrated' and story.plot.stress==90 and story.plot.attempts==0
 private=plot_context(state.model_copy(update={'night_story':story}),'rubiao',{'florenca':'Florença'})
 assert private['estresse']==90 and 'frustrado' in private['lembranca']
 assert plot_context(state,'capitu',{}) is None

def test_two_distinct_crime_authors_in_one_night_and_stable_rolls(monkeypatch):
 game,state=scenario()
 monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a:0.)
 story,attacks=resolve_story(state,game,lambda *a,**k:'capitu')
 assert len(attacks)==2 and len({v for _,v,_ in attacks})==2
 assert resolve_story(state,game,lambda *a,**k:'capitu')==(story,attacks)
 assert story.plot.status=='succeeded'

def test_police_and_deaths_prevent_civil_action(monkeypatch):
 game,state=scenario();monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a:0.)
 story,attacks=resolve_story(state.model_copy(update={'detained_npc_id':'rubiao'}),game,lambda *a,**k:'capitu')
 assert all(cause!='civil' for _,_,cause in attacks) and story.plot.attempts==0


def test_useful_is_supported_information_not_a_truth_or_role_label():
 observations={'apoios_de_conversa':[{'statement':'Bentinho e Escobar estudaram juntos no seminário.'}]}
 assert useful_report('Bentinho e eu estudamos juntos no seminário.',observations)
 assert not useful_report('Boa tarde!',observations)
 assert not useful_report('A verdade é um mar de sombras.',observations)
 assert not useful_report('Escobar é o assassino, com certeza.',observations)
 assert not useful_report('Eu estava no cais.',observations,kind='alibi',suggested=True,quote='texto que o jogador escreveu')

def test_useful_metadata_is_persisted_and_never_given_to_player_text():
 npc=ConversationMessage(id=uuid4(),sender_id='capitu',content='Reconheço a marca do leque.',created_at=NOW,narrative_authorized=True,useful=True)
 assert public_message(npc).useful
 assert not public_message(npc.model_copy(update={'sender_id':'player'})).useful
 assert not public_message(npc.model_copy(update={'narrative_authorized':False})).useful
 assert ConversationMessage.model_validate_json(npc.model_dump_json())==npc


def test_civil_confession_of_real_murder_does_not_win_or_expose_wolf():
 game,state=scenario()
 crime=make_crime(game,1,'florenca','praca_verde',NOW,killer_id='rubiao',cause='civil')
 state=state.model_copy(update={'crimes':(*state.crimes,crime)})
 incoming=ConversationMessage(id=uuid4(),sender_id='player',content='O que fez com Florença?',created_at=NOW)
 outgoing=ConversationMessage(id=uuid4(),sender_id='rubiao',content='Eu matei Florença. Me entrego ao delegado.',created_at=NOW,narrative_authorized=True)
 assessment=local_assessment(incoming.content,outgoing.content,1)
 result=dialogue_transition(state,game,'rubiao',uuid4(),incoming,outgoing,assessment,NOW)
 assert result.state.status=='active' and result.state.phase=='day'
 assert result.state.dialogue_events[-1]['civil_admission']
 assert any(e.type=='civil_crime.admitted' for e in result.events)

@pytest.mark.parametrize('method,fragment',[('detention','se transformou na cela'),('confession','admitiu'),('assembly','assembleia')])
def test_master_final_paper_uses_actual_ending_without_inventing_transformation(method,fragment):
 game,state=scenario();state=state.model_copy(update={'status':'won','phase':'finished','ending_method':method})
 paper=final_edition(state,{'bentinho':'Bentinho'},werewolf_id='bentinho')
 assert fragment in paper.body and 'Floriano' in paper.headline
 if method!='detention':assert 'se transformou na cela' not in paper.body
 assert len(paper.body.split())<80


def test_only_own_feelings_survive_harness_context_projection():
 from src.modules.characters.repository import CatalogCharacterRepository
 import asyncio
 profile=asyncio.run(CatalogCharacterRepository().get('capitu'))
 feelings=[{'por':'bentinho','sentimento':'ódio e amor'}]
 observations={'memoria_social':{'sentimentos_proprios':feelings},'seu_conflito_privado':None}
 context=compact_observations(profile,observations,'O que sente por Bentinho?')
 assert context['memoria_social']['sentimentos_proprios']==feelings

@pytest.mark.anyio
async def test_transactional_night_publishes_both_deaths_but_no_private_plot(inquiry,monkeypatch):
 state=await inquiry.turns.sync(inquiry.game.id)
 state=state.model_copy(update={'night_story':NightStory(seed='integration',plot=MurderPlot(planner_id='rubiao',target_id='florenca'))})
 await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
 monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a:0.)
 monkeypatch.setattr('src.modules.investigation.rules.choose_victim',lambda *a,**k:'bentinho')
 inquiry.clock[0]=state.phase_ends_at+timedelta(seconds=8)
 public=await inquiry.service.get(inquiry.game.id)
 assert public.day==2 and len(public.crimes)==3 and public.status=='active'
 private=await inquiry.turns.sync(inquiry.game.id)
 assert [c.cause for c in private.crimes[-2:]]==['werewolf','civil']
 assert private.crimes[-1].killer_id=='rubiao'
 assert 'Florença' in public.journal[-1].body and 'Bentinho' in public.journal[-1].body
 payload=public.model_dump_json()
 for name in ('night_story','planner_id','killer_id','cause','stress','seed'):
  assert f'"{name}"' not in payload
 saved=await inquiry.storage.games.get(inquiry.game.id)
 assert not next(m for m in saved.characters if m.character_id=='florenca').alive
 again=await inquiry.service.get(inquiry.game.id)
 assert again==public

@pytest.mark.anyio
async def test_ordinary_detainee_does_not_win_and_paper_does_not_name_wolf(inquiry,monkeypatch):
 state=await inquiry.turns.sync(inquiry.game.id)
 state=state.model_copy(update={'detained_npc_id':'rubiao','night_story':NightStory(seed='detained',plot=MurderPlot(planner_id='rubiao',target_id='florenca'))})
 await inquiry.storage.client.set(inquiry.key+':investigation',state.model_dump_json())
 monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a: .99)
 inquiry.clock[0]=state.phase_ends_at+timedelta(seconds=8)
 public=await inquiry.service.get(inquiry.game.id)
 assert public.status=='active' and public.ending is None and public.journal[-1].detention_outcome=='released'
 assert len(public.crimes)==1 and public.journal[-1].victim_id is None
 assert 'lobisomem' not in public.journal[-1].body


def test_current_matrix_is_preserved_when_topics_are_initialized():
 state=SocialState(game_id=uuid4(),relationships=initial_relationships(IDS[:-1]))
 migrated=seed_social_state(state,IDS[:-1],NOW)
 assert {(r.actor_id,r.target_id):r for r in migrated.relationships}=={(r.actor_id,r.target_id):r for r in state.relationships}


def test_protected_last_victim_still_counts_as_a_quiet_wolf_night(monkeypatch):
 game,state=scenario();monkeypatch.setattr('src.modules.investigation.night_story.roll',lambda *a:.99)
 state=state.model_copy(update={'night_story':state.night_story.model_copy(update={'plot':None})})
 story,attacks=resolve_story(state,game,lambda *a,**k:None)
 assert not attacks and story.skipped_nights==1
 story,attacks=resolve_story(state.model_copy(update={'day':2,'night_story':story}),game,lambda *a,**k:'capitu')
 assert attacks==(('bentinho','capitu','werewolf'),)

@pytest.mark.parametrize('speech',[
 'Não matei Florença. Me entrego ao delegado.',
 'Ele disse: “Eu matei Florença.” Aceito a prisão.',
 'Se eu matei Florença, pode me prender.',
])
def test_negation_quote_and_hypothesis_are_not_civil_confessions(speech):
 game,state=scenario();crime=make_crime(game,1,'florenca','praca_verde',NOW,killer_id='rubiao',cause='civil')
 state=state.model_copy(update={'crimes':(*state.crimes,crime)})
 incoming=ConversationMessage(id=uuid4(),sender_id='player',content='O que aconteceu?',created_at=NOW)
 outgoing=ConversationMessage(id=uuid4(),sender_id='rubiao',content=speech,created_at=NOW,narrative_authorized=True)
 result=dialogue_transition(state,game,'rubiao',uuid4(),incoming,outgoing,local_assessment(incoming.content,speech,1),NOW)
 assert not result.state.dialogue_events[-1]['civil_admission'] and result.state.status=='active'
