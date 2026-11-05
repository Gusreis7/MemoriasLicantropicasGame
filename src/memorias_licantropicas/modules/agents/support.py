"""Apoios curtos e verificáveis para a conversa; não geram fatos novos."""
import re
import unicodedata

NAMES = {'player':'Floriano','bentinho':'Bentinho','capitu':'Capitu','escobar':'Escobar',
         'rubiao':'Rubião','virgilia':'Virgília','florenca':'Florença','bacamarte':'Bacamarte'}
STOP = {'para','pelo','pela','como','isso','essa','esse','esta','este','voce','floriano','detetive','sobre','tenho','posso','dizer','pessoa','pessoas','coisa','coisas','mais','muito','ainda','apenas','nada','tudo','aqui','nao','com','que','uma','por','dos','das','seu','sua'}


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))


def words(text):
    return {w for w in re.findall(r'[a-z]+',normalized(text)) if len(w)>2 and w not in STOP}


def is_greeting(question):
    return bool(re.fullmatch(r'\s*(?:ola|oi|bom dia|boa tarde|boa noite|salve)\b[^?!]*[.!?]*\s*', normalized(question)))


def is_courtesy_reply(question, reply):
    """Vocabulário fechado para cortesia sem fatos, segredos ou confissões."""
    if not (is_greeting(question) or re.search(r'\bfale comigo\b',normalized(question))):
        return False
    tokens=re.findall(r'[a-z]+',normalized(reply))
    allowed=set(('ola oi bom boa dia tarde noite saudacoes salve floriano detetive senhor senhora sr meu minha caro cara homem '
        'que prazer muito ve lo la lhe te voce ver por aqui estar estou sou sim nao apenas e o a os as '
        'em com como vai seu sua hoje pode me chamar de capitu rubiao diga logo direto franca francamente '
        'fale falar aberto aberta voce deseja desejo quer quero saber pergunta perguntar saber conversar conversa '
        'o traz estas bandas lados util posso ajudar posso ajudo pois bem seja bem vindo obrigada obrigado '
        'tudo bem o que isso por favor falar comigo disposicao qual duvida tem deseja esclarecer').split())
    return bool(tokens) and len(tokens)<=35 and set(tokens)<=allowed


def dialogue_focus(question, observations):
    text=normalized(question)
    if is_greeting(question):
        return 'A mensagem atual é apenas uma saudação. Cumprimente Floriano brevemente na sua voz, sem introduzir pistas, suspeitos ou acontecimentos.'
    if re.search(r'\bacredita\b.*\blobisome',text):
        return 'A pergunta atual é sobre sua crença em lobisomens. Diga se acredita, duvida ou não sabe, em primeira pessoa. Não invente conversas ou fontes para justificar sua opinião.'
    if re.search(r'\bfale comigo\b',text):
        return 'Floriano está pedindo uma conversa direta. Responda à impaciência dele e peça que esclareça o que deseja saber. Não repita seu objetivo pessoal ou pistas anteriores.'
    if not (observations or {}).get('apoios_de_conversa') and re.search(r'\bbras cubas\b',text):
        return 'A pergunta atual é sobre Brás Cubas. Você não tem fatos autorizados sobre inimigos ou motivos contra ele. Diga francamente que não sabe apontar alguém; não invente dívidas, brigas ou suspeitos.'
    return 'Responda à última mensagem de Floriano. Seus objetivos influenciam seu tom, mas não substituem o assunto da pergunta. Não apresente as palavras dele como uma descoberta sua.'


def historical_dialogue_content(content):
    """Retira apenas a moldura legada no prompt; o histórico salvo é preservado."""
    prefixes=('Uma coisa eu lhe digo:', 'Posso lhe ajudar com isso:',
              'Posso lhe contar uma coisa:', 'Isso eu posso lhe contar:',
              'Pois escute:', 'Vamos ao que importa:', 'Comecemos pelo que sabemos:')
    if not content.startswith(prefixes):
        return content
    statement=content.split(':',1)[1].strip()
    return re.split(r'(?<=\.)\s+(?:Compare |Converse com |Ouça |Pergunte também )',statement,maxsplit=1)[0]




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
    if is_greeting(question):
        return ()
    # O nome usado como vocativo não torna todos os fatos do próprio NPC
    # relevantes: "acredita em lobisomens, Rubião?" não pede seu namoro.
    query=words(question)-words(profile.name)
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
        if entry.get('origem') != 'authored' and 'mostro-lhe' in normalized(statement):
            # A apresentação de um objeto pelo jogador não é descoberta nova.
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
    # Uma pergunta específica não autoriza trocar de assunto só porque há
    # testemunhos ou rumores disponíveis. Saudações não pedem pistas.
    subjects = [normalized(name) for identifier,name in {**NAMES, 'bras_cubas':'Brás Cubas'}.items()
                if identifier not in ('player', profile.id) and normalized(name) in normalized(question)]
    candidates = [candidate for candidate in candidates
                  if (candidate['relevance'] > 0 or asks_for_guidance(question))
                  and (not subjects or any(subject in normalized(candidate['statement']) for subject in subjects))]
    candidates.sort(key=lambda c:(c['relevance'],c['priority']),reverse=True)
    selected=[];seen=set()
    for candidate in candidates:
        if candidate['statement'] in seen:continue
        seen.add(candidate['statement']);selected.append(candidate)
        if len(selected)==3:break
    return tuple(selected)






def compact_observations(profile, observations, question):
    if observations is None:return None
    supports=dialogue_supports(profile,observations,question)
    result={key:observations[key] for key in ('dia','fase','seu_conflito_privado','ultimo_objeto_apresentado','suas_atividades','seus_depoimentos_registrados','suas_versoes_de_interrogatorio','seus_confrontos') if key in observations}
    # A memória também explica emoções e reações, mesmo sem ser uma pista
    # lexicalmente ligada à pergunta. A projeção já pertence apenas a este NPC.
    social=observations.get('memoria_social',{})
    result['memoria_social']={key:social.get(key,[]) for key in ('confidencias_autorizadas','descobertas_autorizadas','relacao_com_interlocutor','sentimentos_proprios')}
    result['apoios_de_conversa']=supports
    result['memoria_social']['memorias_relevantes']=[entry for entry in social.get('memorias_relevantes',())
        if entry.get('compartilhavel',True)
        and (entry.get('visibilidade')!='private' or entry.get('compartilhavel') is True)][:12]
    result['memoria_social']['encontros_anteriores']=social.get('encontros_anteriores',())[-3:]
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
    return bool(re.search(
        r'\b(?:por onde|como|onde) (?:eu )?(?:comeco|comecar|investigar|procuro|procurar)\b|'
        r'\b(?:alguma|uma|tem|teria) (?:pista|sugestao|informacao)\b|'
        r'\b(?:pode |poderia )?(?:me )?(?:ajudar|orientar)\b|'
        r'\b(?:o que|que) (?:voce |o senhor |a senhora )?(?:sabe|conhece|pode me contar)\b|'
        r'\b(?:conte|contar|fale)\b.{0,25}\b(?:sabe|amizade|investigacao|pistas)\b',text))
