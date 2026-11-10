# NPCs e mestre da mesa

Queria que conversar com os suspeitos fosse uma parte real da investigação, sem
deixar o modelo decidir quais fatos aconteceram. Por isso, separei a **mesa**,
que mantém as regras e o estado da partida, dos **agentes**, que recebem apenas
o conhecimento permitido a cada personagem.

A versão atual usa **Qwen3-32B pelo Amazon Bedrock Mantle** para os diálogos.
Não há um provedor de LLM local pronto para substituí-lo. Sem acesso ao Bedrock,
a aplicação pode iniciar, mas não oferece a experiência completa de conversa.

## O caminho de uma conversa

Quando Floriano pergunta algo, o servidor confere a partida, a proximidade e a
disponibilidade do personagem. Depois, busca as informações permitidas para
responder. O personagem admite quando não sabe e avisa quando já contou tudo
sobre um assunto. Um pedido para repetir pode retomar o relato, sem criar outra prova.

O modelo recebe formulações autorizadas e escolhe como combiná-las. A saída é um
`TableDeliveryPlan`, validado por Pydantic e pelo parser de ferramentas do
LangChain. Não há campo para o modelo inventar texto factual. Se ele atrasar,
ficar indisponível ou escolher uma opção inválida, o servidor usa a resposta das
regras. Erros inesperados e cancelamentos encerram a troca.

A conversa usa um grafo LangGraph com três etapas:
`prepare_table → native_table_delivery → revalidate_persist`.
`HarnessService.graph` expõe o grafo em uso. Não há memória paralela no grafo:
Redis guarda os dados, e um outbox permite concluir uma gravação interrompida
sem duplicar mensagens ou provas.

Enquanto o modelo responde, a reserva de ações do jogador fica livre. A mesma
conversa não aceita outra mensagem simultânea. Antes de salvar, o servidor
confere novamente o NPC, o dia e os fatos permitidos. Uma resposta desatualizada
é descartada. A tentativa de apresentação tem prazo limitado; no padrão atual,
são até seis segundos. Os rastros distinguem as causas de falha sem guardar
prompts, falas ou segredos, e o rastreamento externo do LangSmith fica desativado.

## Álibis e testemunhas

Duas pessoas que passaram a noite juntas compartilham o mesmo registro de local
e período. O relato da primeira aguarda confirmação; ao ouvir a outra, Floriano
obtém a confirmação recíproca. Não há álibis falsos nesta versão.

A fera passa a noite sozinha, mas civis também podem ficar sozinhos. Falta de
companhia, cobertura parcial e ausência de informação são situações diferentes.
Uma observação de alguém na rua não equivale a presenciar o ataque. O início da
partida garante uma observação por um sobrevivente, sem revelar o papel secreto
como se fosse um fato conhecido por ele.

O delegado avalia as provas selecionadas, suas fontes e a noite a que se referem.
Um álibi confirmado cobre aquele período, não todas as noites. Os relatos úteis
aparecem em roxo e dourado, com seu estado de confirmação.

## Fofocas e segredos

Relações, confiança e ressentimento influenciam o que cada personagem pode
compartilhar. Isso permite suspeitas e acusações pessoais sem dar acesso aos
segredos dos outros. A fala de Floriano continua atribuída a ele; não se torna
verdade só porque foi repetida por um NPC.

O conhecimento preserva sua origem. Várias pessoas repetindo uma fofoca não
viram testemunhas independentes. Informações novas podem reabrir um assunto
esgotado, mantendo a mesma origem quando forem apenas uma correção.

Cada personagem é um agente lógico com identidade fixa e consultas limitadas.
Não é um processo com acesso livre ao banco. Os encontros entre NPCs têm um
fluxo LangGraph próprio, com agenda e limites de consumo; a IA só escolhe entre
alegações já autorizadas ou encerra a conversa.

## O mestre da mesa e o jornal

O mestre aplica relatos verificados e prepara a narrativa das consequências.
Depois de uma prisão, ele pode gerar o editorial em segundo plano durante a
animação de suspense. O texto só aparece quando as regras confirmam o resultado
e os fatos ainda correspondem àquela prisão. Se a geração falhar ou não terminar,
o jornal usa a edição prevista pelas regras sem esperar pelo modelo.

Para acompanhar o código, comece em `src/composition.py` e nos módulos `agents`,
`table`, `knowledge`, `social` e `session_master`. Os comandos de verificação estão
em [testes](testes.md).
