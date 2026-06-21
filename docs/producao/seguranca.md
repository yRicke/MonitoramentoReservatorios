# Seguranca

## Controles existentes

O sistema ja possui alguns controles basicos:

- autenticacao web por usuario e senha do Django;
- token individual por reservatorio para o ESP32;
- comparacao segura do token via `compare_digest`;
- painel do ESP32 protegido por rota com a senha do AP;
- fluxo ativo sem dependencia de token global em `.env`.

## Gaps atuais confirmados

No estado atual do repositorio:

- `DEBUG = True` em `setup/settings.py`;
- nao ha HTTPS/TLS no fluxo local;
- nao ha trilha formal de auditoria;
- nao ha politica fechada de rotacao operacional de segredos;
- o painel AP do ESP32 e local e simples, sem camadas extras de autenticacao.

## Recomendacoes

- mover segredos reais para variaveis de ambiente apropriadas;
- criar `.env.example`;
- garantir `DEBUG = False` fora de desenvolvimento;
- adicionar reverse proxy com HTTPS;
- revisar exposicao do painel local em campo;
- formalizar logs de autenticacao, ingestao e calibracao.
