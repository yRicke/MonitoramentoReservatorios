# Docs

Esta pasta foi reorganizada com base na sugestao do documento tecnico completo e no estado atual do codigo do repositorio.

## Como ler esta documentacao

- `documentacao-tecnica.md`: resumo executivo tecnico do sistema.
- `arquitetura/`: visao de camadas, fluxo de dados, API do ESP32 e modelo de dados.
- `firmware/`: painel local, pinagem, comissionamento e troubleshooting do ESP32.
- `operacao/`: uso diario da plataforma web, cadastro, calibracao, alerta sonoro e relatorios.
- `producao/`: estado atual de deploy, seguranca, backup e checklist para endurecimento.
- `mestrado/`: materiais de enquadramento academico e protocolo aplicado.
- `anexos/`: payloads, glossario, checklists e pendencias.

## Convencoes adotadas

- Implementado: confirmado no codigo Django, firmware, templates, models, rotas ou testes.
- Legado/compatibilidade: ainda existe para migracao ou alias interno, mas nao deve ser tratado como fluxo novo.
- Melhoria futura: recomendacao tecnica para evolucao, ainda nao consolidada no fluxo ativo.

## Estado atual

O sistema continua sendo um prototipo local avancado, com operacao funcional entre Django e ESP32, ponto canonico unico por reservatorio, calibracao assistida, alerta sonoro remoto e relatorio imprimivel pelo navegador.
