# Deploy

## Estado atual

O repositorio esta pronto para execucao local e homologacao tecnica, mas ainda nao traz uma estrategia fechada de deploy produtivo.

Pontos confirmados hoje:

- backend Django funcional localmente;
- banco padrao local;
- firmware apontando para IP do Django configurado manualmente;
- relatorios e painel web operando em rede local.

## Subida local basica

Fluxo comum para ambiente local:

1. instalar dependencias de `requirements.txt`;
2. aplicar migracoes do Django;
3. criar usuario;
4. subir o servidor em endereco acessivel ao ESP32;
5. configurar o `ip_django` no painel local do firmware.

Exemplo:

```powershell
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

## Melhorias recomendadas antes de producao

- migrar de banco local para PostgreSQL;
- desligar `DEBUG`;
- definir variaveis de ambiente versionadas por exemplo, nao por segredo real;
- padronizar logs e auditoria;
- documentar topologia final de rede;
- definir empacotamento do backend e estrategia de atualizacao do firmware.
