# Alerta Sonoro

## Quando o buzzer deve apitar

O firmware ativa o buzzer quando o backend informa `alerta_sonoro_ativo=true`.

No dominio atual, isso acontece quando:

- o reservatorio esta em `perigo`; e
- nao houve silenciamento temporario; e
- nao houve silenciamento permanente.

O teste manual do buzzer tambem ativa o alerta independentemente do status, por tempo limitado.

## Cadencia atual

Valores enviados pelo backend:

- ligado: `500 ms`
- desligado: `500 ms`

## Controles na interface web

A tela de detalhe e a tela dedicada do alerta permitem:

- silenciar alerta no estado atual de perigo;
- reativar alerta;
- silenciar permanentemente;
- reativar alerta permanente;
- testar alerta sonoro por `5 segundos`.

## Comportamentos importantes

- se o reservatorio sair de `perigo`, o silenciamento temporario e limpo automaticamente;
- o silenciamento permanente permanece ate reativacao manual;
- o teste nao deve ser disparado novamente enquanto ja estiver em andamento.
