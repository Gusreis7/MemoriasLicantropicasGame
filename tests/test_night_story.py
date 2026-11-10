from datetime import UTC, datetime
from uuid import uuid4
import pytest
from src.contracts.model import GameState, GameCharacter
from src.contracts.investigation import NightStory,MurderPlot
from src.modules.knowledge.affects import IDS
from src.modules.investigation.rules import make_initial_investigation, choose_victim
from src.modules.investigation.night_story import resolve_story,civil_probability,plot_context

NOW=datetime(2026,11,4,12,tzinfo=UTC)

def cast():
 return GameState(id=uuid4(),created_at=NOW,content_version='3',characters=tuple(
  GameCharacter(character_id=p,role='werewolf' if p=='bentinho' else 'civil') for p in IDS[:-1]))

def scenario():
 game=cast();state=make_initial_investigation(game,NOW)
 return game,state.model_copy(update={'night_story':NightStory(seed='fixed',plot=MurderPlot(planner_id='rubiao',target_id='florenca'))})


@pytest.mark.parametrize('night,p',[(1,.25),(2,.125),(3,.0625),(4,.03125)])
def test_plot_chance_halves_by_calendar_night(night,p):assert civil_probability(night)==p


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


