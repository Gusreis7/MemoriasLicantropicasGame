"""Apoios curtos e verificáveis para a conversa; não geram fatos novos."""
import re
import unicodedata

NAMES = {'player':'Floriano','bentinho':'Bentinho','capitu':'Capitu','escobar':'Escobar',
         'rubiao':'Rubião','virgilia':'Virgília','florenca':'Florença','bacamarte':'Bacamarte'}
STOP = {'para','pelo','pela','como','isso','essa','esse','esta','este','voce','floriano','detetive','sobre','tenho','posso','dizer','pessoa','pessoas','coisa','coisas','mais','muito','ainda','apenas','nada','tudo','aqui','nao','com','que','uma','por','dos','das','seu','sua'}
OPENERS = {'bentinho':'Uma coisa eu lhe digo:', 'capitu':'Posso lhe ajudar com isso:',
 'escobar':'Posso lhe contar uma coisa:', 'rubiao':'Isso eu posso lhe contar:',
 'virgilia':'Pois escute:', 'florenca':'Vamos ao que importa:', 'bacamarte':'Comecemos pelo que sabemos:'}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def words(text):
    return {w for w in re.findall(r'[a-z]+',normalized(text)) if len(w)>2 and w not in STOP}


def _authored_voice(statement, npc_id):
    """Only authored canonical facts change grammatical voice; quoted testimony never does."""
    forms = {
        'casamento': {
            'capitu':'Eu sou casada com Bentinho; o ciúme dele tem provocado discussões.',
            'bentinho':'Eu sou casado com Capitu; meu ciúme tem provocado discussões.',
        },
        'amizade': {
            'capitu':'Escobar e eu somos amigos e nos encontramos nos parques e no trabalho. Isso alimenta o ciúme de Bentinho.',
            'escobar':'Capitu e eu somos amigos e nos encontramos nos parques e no trabalho. Isso alimenta o ciúme de Bentinho.',
        },
        'seminario': {
            'bentinho':'Escobar e eu estudamos juntos no seminário e mantivemos uma ligação antiga.',
            'escobar':'Bentinho e eu estudamos juntos no seminário e mantivemos uma ligação antiga.',
        },
        'tratamento': {
            'bentinho':'Eu faço acompanhamento com Bacamarte, mas resisto às consultas e à medicação. Não sei confirmar cada dose.',
            'bacamarte':'Eu acompanho Bentinho, que resiste às consultas e à medicação. Não sei confirmar cada dose.',
        },
        'internacao': {
            'florenca':'Contesto Bacamarte por ter internado meu pai e procuro quem me escute.',
            'bacamarte':'Florença me contesta por eu ter internado o pai dela e procura quem a escute.',
        },
        'aproximacao': {
            'rubiao':'Tento aproximar-me de Florença, embora ela não corresponda e se incomode com minha insistência.',
            'florenca':'Rubião tenta aproximar-se de mim, embora eu não corresponda e me incomode com a insistência.',
        },
    }
    prefixes = (
        ('Capitu e Bentinho são casados;', 'casamento'),
        ('Capitu e Escobar são amigos e se encontram', 'amizade'),
        ('Bentinho e Escobar estudaram juntos no seminário', 'seminario'),
        ('Bentinho faz acompanhamento com Bacamarte, mas resiste', 'tratamento'),
        ('Florença contesta Bacamarte por ter internado seu pai', 'internacao'),
        ('Rubião tenta aproximar-se de Florença, embora ela não corresponda', 'aproximacao'),
    )
    for prefix,topic in prefixes:
        if statement.startswith(prefix):
            return forms[topic].get(npc_id,statement)
    return statement


def _lead(statement, npc_id):
    text=normalized(statement)
    if 'seminario' in text:
        other='Escobar' if npc_id=='bentinho' else 'Bentinho' if npc_id=='escobar' else 'Bentinho ou Escobar'
        return f'Pergunte também a {other} como foi essa amizade no seminário.'
    if 'medicacao' in text or 'consultas' in text:
        if npc_id=='bacamarte': return 'Converse com Bentinho sobre as consultas.'
        if npc_id=='bentinho': return 'Converse com Bacamarte sobre o acompanhamento.'
        return 'Converse com Bacamarte sobre o acompanhamento e com Bentinho sobre as consultas.'
    if 'internado' in text or 'internou' in text:
        if npc_id=='florenca': return 'Pergunte a Bacamarte por que decidiu internar meu pai.'
        return 'Florença pode lhe contar por que contesta a internação do pai.'
    if 'casad' in text or 'ciume' in text:
        if npc_id=='bentinho': return 'Ouça também Capitu sobre essas discussões.'
        if npc_id=='capitu': return 'Ouça também Bentinho sobre essas discussões.'
        return 'Ouça Capitu e Bentinho separadamente sobre essas discussões.'
    if 'amizade' in text or 'amigos' in text:
        others=[name for identifier,name in NAMES.items() if identifier not in (npc_id,'player') and normalized(name) in text]
        if others:return f'Pergunte também a {" ou ".join(others[:2])} pela versão dessa amizade.'
        return 'Compare essa amizade com os relatos que já anotou no caderno.'
    if 'objeto' in text or 'peca' in text:
        return 'Compare esta informação com o que outra testemunha reconhece.'
    return 'Compare esse relato com os que já anotou no caderno.'


def is_alibi_question(question):
    text=normalized(question)
    return bool(re.search(
        r'\b(?:onde|aonde)\s+(?:(?:voce|o senhor|a senhora)\s+)?(?:estava|esteve|ficou|passou|andou)\b|'
        r'\bcom quem\b.{0,35}\b(?:estava|esteve|ficou|passou|andou|jantou|saiu)\b|'
        r'\b(?:estava|esteve|ficou|passou|andou)\b.{0,35}\bcom quem\b|'
        r'\b(?:o que|que)\s+(?:voce\s+)?(?:fazia|estava fazendo|fez)\b|'
        r'\b(?:qual|seu) alibi\b',text))


def dialogue_supports(profile, observations, question):
    """Lista somente o que a persona pode compartilhar agora, com origem estável."""
    if observations is None:
        return ()
    query=words(question)
    candidates=[]
    for index, record in enumerate(observations.get('seus_depoimentos_registrados',())):
        statement=record.get('fala','')
        if record.get('nome'): statement=f"Sobre {record['nome']}: {statement}"
        if statement:
            candidates.append({'id':f"testimony:{record.get('evidence_id',index)}",'statement':statement,
                'lead':'Compare este objeto com os depoimentos já anotados no caderno.', 'kind':'testimony','priority':5})
    for index, record in enumerate(observations.get('suas_atividades',())):
        statement=record.get('lembranca') or record.get('fala','')
        if statement:
            candidates.append({'id':f'activity:{record.get("dia",index)}:{record.get("periodo","")}',
                'statement':statement,'lead':'Confronte essa lembrança com a versão de quem estava por perto.',
                'kind':'activity','priority':4 if is_alibi_question(question) else 0})
    active=observations.get('ultimo_objeto_apresentado') or {}
    if active.get('fala_registrada'):
        candidates.append({'id':f"active-item:{active.get('evidence_id',active.get('item_id',''))}",
            'statement':f"Sobre {active.get('nome','essa peça')}: {active['fala_registrada']}",
            'lead':'Compare este objeto com os depoimentos já anotados no caderno.',
            'kind':'testimony','priority':8})
    social=observations.get('memoria_social',{})
    for index,entry in enumerate(social.get('memorias_relevantes',())):
        if entry.get('compartilhavel',True) is False:
            continue
        # Private entries are projected only after authorization by KnowledgeService.
        if entry.get('visibilidade')=='private' and not entry.get('compartilhavel',False):
            continue
        statement=entry.get('conteudo','')
        if not statement or entry.get('tipo')=='literal':
            continue
        speaker=entry.get('quem_falou')
        if entry.get('origem')!='authored' and speaker and speaker!=profile.id:
            statement=f"Ouvi de {NAMES.get(speaker,speaker)}: {statement}"
        candidates.append({'id':str(entry.get('claim_id',f'memory:{index}')),
            'statement':statement,'lead':_lead(statement,profile.id),'kind':'social','authored':entry.get('origem')=='authored',
            'priority':2 if entry.get('origem')=='authored' else (9 if not asks_for_guidance(question) else 0)})
    # Do not fall back to an unrelated inventory or private biography.
    for candidate in candidates:
        candidate['relevance']=len(query & words(candidate['statement']))
    candidates.sort(key=lambda c:(c['relevance'],c['priority']),reverse=True)
    selected=[];seen=set()
    for candidate in candidates:
        if candidate['statement'] in seen:continue
        seen.add(candidate['statement']);selected.append(candidate)
        if len(selected)==3:break
    return tuple(selected)


def supported_reply(profile, observations, question, support_id=None):
    supports=(observations or {}).get('apoios_de_conversa') or dialogue_supports(profile,observations,question)
    if not supports:
        return None
    chosen=next((s for s in supports if s['id']==support_id),supports[0])
    statement=chosen['statement'].strip()
    if chosen.get('authored',False): statement=_authored_voice(statement,profile.id)
    return f"{OPENERS.get(profile.id,'Posso lhe contar o seguinte:')} {statement} {chosen['lead']}"


def has_useful_anchor(content, supports):
    """Triagem conservadora de utilidade, não uma prova de verdade semântica."""
    actual=words(content)
    for support in supports:
        expected=words(support['statement'])
        overlap=actual & expected
        # Merely repeating names is not useful testimony.
        meaningful=overlap-{normalized(n) for n in NAMES.values()}
        if len(meaningful)>=2 and len(overlap)>=min(4,max(2,len(expected)//3)):
            return True
    return False


def compact_observations(profile, observations, question):
    if observations is None:return None
    supports=dialogue_supports(profile,observations,question)
    result={key:observations[key] for key in ('dia','fase','seu_conflito_privado','ultimo_objeto_apresentado','suas_atividades','seus_depoimentos_registrados','suas_versoes_de_interrogatorio','seus_confrontos') if key in observations}
    # Facts not chosen as supports remain unavailable for embellishment.
    social=observations.get('memoria_social',{})
    result['memoria_social']={key:social.get(key,[]) for key in ('confidencias_autorizadas','descobertas_autorizadas','relacao_com_interlocutor','sentimentos_proprios')}
    result['apoios_de_conversa']=supports
    result['memoria_social']['memorias_relevantes']=[entry for entry in social.get('memorias_relevantes',()) if str(entry.get('claim_id')) in {s['id'] for s in supports}]
    result['memoria_social']['fontes_conhecidas']=sorted({entry.get('quem_falou') for entry in social.get('memorias_relevantes',()) if entry.get('quem_falou')} | {entry.get('interlocutor_id') for entry in social.get('encontros_anteriores',()) if entry.get('interlocutor_id') and entry.get('falas')})
    return result


def unauthorized_personal_disclosure(npc_id,content,observations):
    """Guard local para admissões íntimas autorais; opinião alheia não é confissão."""
    allowed=set((observations or {}).get('memoria_social',{}).get('descobertas_autorizadas',()))
    text=normalized(content)
    text=re.sub(r'[«“"].*?[»”"]','',text,flags=re.S)
    for clause in re.split(r'[.!?;\n]+',text):
        if re.search(r'\b(nao sou|nao sinto|nao amo|nao quero|nao pretendo|nunca quis|dizem que|ouvi dizer|segundo)\b',clause):continue
        if npc_id=='escobar' and 'escobar_affection' not in allowed:
            if re.search(r'\b(sou .{0,30}amig.{0,12}que o ama|amo.{0,25}bentinho|apaixon.{0,30}bentinho|sinto.{0,35}(?:alem da amizade|amor)|bentinho.{0,45}(?:alem da amizade|meu amor))\b',clause):
                return True
        if npc_id=='capitu' and 'capitu_separation' not in allowed:
            if re.search(r'\b(quero|desejo|penso|pretendo|decidi|vou)\b.{0,25}\b(separar|separar-me|deixar meu marido|deixar bentinho)\b',clause):
                return True
    return False


def asks_for_guidance(question):
    text=normalized(question)
    return not re.search(r'\b(aborrecid[ao]|zangad[ao]|brav[ao]|irritad[ao])\b.{0,20}\bcomigo\b|\bcomo (?:voce |o senhor |a senhora )?se sente\b',text)
