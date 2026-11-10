# Documentação

O [README principal](../README.md) apresenta o jogo, a proposta da investigação,
os controles e as limitações da versão atual. Deixei os detalhes de execução e
arquitetura nos guias abaixo para não transformar a apresentação em um manual
de infraestrutura.

| Guia | Conteúdo |
| --- | --- |
| [Reprodução local](deploy_local.md) | Instalar, configurar o Bedrock e preservar partidas |
| [Reprodução na AWS](reproducao_aws.md) | Criar uma instalação própria com Terraform e GitHub Actions |
| [Arquitetura AWS](solucao_aws.md) | Rede, persistência, segurança e deploy |
| [NPCs e mestre da mesa](orquestracao_agentes.md) | Regras, conhecimento e fluxo das conversas |
| [Testes](testes.md) | Testes automatizados e avaliações com modelo real |
| [Uso de IA e Codex](uso_ia_e_codex.md) | LLMs no jogo e programação guiada |
| [Créditos dos efeitos](creditos_efeitos_open_source.md) | Fontes, licenças e agradecimentos |

**Estado atual:** as conversas usam Qwen3-32B no Amazon Bedrock Mantle. O projeto
foi desenvolvido com créditos da AWS, mas a reprodução exige acesso próprio ao
serviço e pode gerar custos. Ainda não há suporte pronto a modelos locais.
