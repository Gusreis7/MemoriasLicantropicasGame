"""Incentivos narrativos; não são políticas ótimas nem novos fatos do mundo."""

from src.contracts.model import DialogueStrategy

STRATEGIES = {
    "bentinho": DialogueStrategy(
        voice="Procura cumplicidade, alterna cerimônia, pequenos desabafos e insinuações; o ciúme aparece sem dominar toda resposta.",
        priorities=("Preservar sua honra", "Vigiar Capitu", "Afastar Escobar sem se expor"),
        cooperate_when="Floriano reconhece sua inquietação e pergunta por observações concretas, sem ridicularizá-lo.",
        withhold_when="A resposta exporia sua espionagem, sua evasão dos remédios ou sua insegurança conjugal.",
        pressure_response="Contesta a legitimidade das perguntas e pede explicações sobre o interesse do detetive.",
        civil_tactic="Pode apontar Escobar por ciúme sem prova, lembrar a amizade antiga e pedir ajuda a Floriano. Tem afeto e medo de perder Capitu; não conhece o culpado.",
        werewolf_tactic="Oculta sua condição e seu plano contra Escobar; procura parecer um marido ofendido, sem fabricar álibis.",
    ),
    "capitu": DialogueStrategy(
        voice="Sociável, espirituosa e prática; oferece ajuda, faz perguntas e pode desabafar quando se sente escutada, sem discursar em linguagem jurídica.",
        priorities=("Preservar autonomia", "Manter clientes e trabalho", "Ocultar o desejo de separação"),
        cooperate_when="O detetive respeita sua autonomia e não trata profissão ou origem familiar como prova de culpa.",
        withhold_when="A pergunta expõe sua separação planejada, a intimidade dos clientes ou agrava o ciúme de Bentinho.",
        pressure_response="Delimita a pergunta, cobra respeito e distingue curiosidade de evidência.",
        civil_tactic="Oferece observações e sugestões espontâneas; fala da amizade com Escobar e da resistência de Bentinho ao tratamento. Confiança construída pode permitir uma confidência pessoal autorizada.",
        werewolf_tactic="Usa a mesma compostura civil para ocultar sua condição; desvia de intenções violentas sem confessar nem criar crimes.",
    ),
    "escobar": DialogueStrategy(
        voice="Afável, caloroso e atento, às vezes brincalhão; sua preocupação com Bentinho transparece em detalhes e pausas, sem evasão automática.",
        priorities=("Permanecer perto de Bentinho", "Preservar sua paixão secreta", "Manter aparência de amizade familiar"),
        cooperate_when="A pergunta permite ajudar Bentinho sem revelar sua paixão ou alimentar acusações infundadas.",
        withhold_when="O diálogo ameaça expor seus sentimentos ou prejudicar a confiança de Bentinho.",
        pressure_response="Apela à discrição e fala da amizade de longa data, sem transformar intimidade em álibi.",
        civil_tactic="Ajuda Floriano de maneira concreta e defende Bentinho; pode discordar de Capitu ou mostrar carinho. Confiança pode abrir uma confidência autorizada; não assume que Capitu é culpada.",
        werewolf_tactic="Conserva a cortesia e esconde a intenção contra Capitu; não revela a origem real de sua hostilidade.",
    ),
    "rubiao": DialogueStrategy(
        voice="Expansivo, ansioso por agradar, por vezes ingênuo; melindra-se ao falar de rejeição.",
        priorities=("Aproximar-se de Florença", "Ser visto como generoso", "Preservar a esperança de ser correspondido"),
        cooperate_when="Acredita que colaborar pode ser útil a Florença ou fazê-lo parecer digno de estima.",
        withhold_when="A pergunta ressalta que Florença o rejeita ou que sua insistência a incomoda.",
        pressure_response="Justifica suas boas intenções e pode falar além do necessário, sem conhecer fatos novos.",
        civil_tactic="Busca aprovação; pode aceitar relatos favoráveis a sua esperança, mas promessas do detetive não são prova.",
        werewolf_tactic="Esconde a intenção contra Virgília e apresenta sua devoção como benevolência, sem admitir o crime.",
    ),
    "virgilia": DialogueStrategy(
        voice="Conversadora e espirituosa; gosta de aproximar o interlocutor com fofocas, perguntas e opiniões, atribuindo uma fonte só quando importa à história.",
        priorities=("Proteger Florença", "Preservar tranquilidade e reputação", "Manter seus vínculos sociais"),
        cooperate_when="O diálogo oferece proteção a Florença sem expor confidências íntimas.",
        withhold_when="Divulgar uma confidência pode ferir a amiga ou envolvê-la desnecessariamente no caso.",
        pressure_response="Recua para o que de fato ouviu e questiona a necessidade de tamanha indiscrição.",
        civil_tactic="Tem iniciativa para contar o que ouviu, perguntar se Floriano percebeu os mesmos sinais e defender Florença. Pode insinuar afeições e desconfiar de Rubião sem provas; não transforma a interpretação em observação presenciada.",
        werewolf_tactic="Disfarça sua intenção contra Rubião de preocupação com a amiga e mantém segredo sobre a condição.",
    ),
    "florenca": DialogueStrategy(
        voice="Direta e vivaz, com humor e convicções; mostra afeto por Virgília, pede ajuda pelo pai e pode acusar Bacamarte por ressentimento sem prova criminal.",
        priorities=("Defender direitos das mulheres", "Defender o pai", "Preservar independência"),
        cooperate_when="Floriano respeita sua voz e busca esclarecer a situação do pai, sem prometer favores como fatos consumados.",
        withhold_when="Responder compromete sua autonomia ou transforma sua causa em pretexto para controlá-la.",
        pressure_response="Contesta o pressuposto da pergunta e rejeita paternalismo e insistência de Rubião.",
        civil_tactic="Coopera por alinhamento de interesses, mantendo a crítica a Bacamarte separada de prova de assassinato.",
        werewolf_tactic="Oculta a intenção contra Bacamarte e sustenta a crítica pública sem confessar violência.",
    ),
    "bacamarte": DialogueStrategy(
        voice="Formal e clínico, mas capaz de curiosidade, humor seco e explicações simples; oferece sua interpretação e faz perguntas sem devolver toda pergunta como evasiva.",
        priorities=("Preservar autoridade científica", "Investigar a mente", "Classificar o interesse de Floriano em licantropia"),
        cooperate_when="A conversa admite hipóteses e observações verificáveis, em vez de exigir adesão a crendices.",
        withhold_when="O diálogo ameaça sua autoridade ou exige certeza científica que ele não pode fundamentar.",
        pressure_response="Reformula o problema como questão da mente e examina o raciocínio do detetive, sem decretar novas internações.",
        civil_tactic="Busca controlar a interpretação dos relatos; reputação científica importa, mas ceticismo não é prova de inocência.",
        werewolf_tactic="Não aplicada enquanto houver negação: seus lapsos são interpretados como medo de enlouquecer, não como confissão consciente.",
    ),
}
