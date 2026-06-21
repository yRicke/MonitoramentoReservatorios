# Backup

## Estado atual

O projeto nao possui uma estrategia oficial de backup automatizado implementada no repositorio.

Riscos associados:

- perda de historico de leituras;
- perda de calibracoes salvas;
- perda de usuarios e reservatorios cadastrados;
- indisponibilidade por corrupcao do banco local.

## O que precisa ser preservado

- banco de dados do Django;
- arquivos de configuracao do ambiente;
- versao do firmware em uso em campo;
- registros operacionais e relatorios relevantes.

## Recomendacao minima

Antes de uso produtivo:

- definir rotina de copia periodica do banco;
- testar restauracao;
- manter copia separada das configuracoes do ambiente;
- versionar o firmware utilizado em cada instalacao de campo.
