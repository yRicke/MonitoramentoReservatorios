# Guia de OperaÃ§Ã£o do Sistema

## 1. Objetivo
Este guia descreve como operar o ambiente completo de monitoramento:
- módulo físico embarcado (ESP32 + sensores).
- módulo de plataforma web/backend (Django).

Foco:
- operaÃ§Ã£o diÃ¡ria;
- checklists de inÃ­cio/fim de turno;
- resposta a incidentes comuns;
- governanÃ§a operacional mÃ­nima.

## 2. Perfis Operacionais
Perfis recomendados:
- **Operador**: acompanha dashboard, analisa alertas e executa procedimentos padrÃ£o.
- **TÃ©cnico de campo**: instala/valida ESP32, sensores e rede local.
- **Administrador**: mantÃ©m backend, usuÃ¡rios, token e disponibilidade do sistema.

## 3. PrÃ©-requisitos Operacionais
### 3.1 Backend (Plataforma)
PrÃ©-requisitos:
- Python compatÃ­vel com Django do projeto;
- banco local (`db.sqlite3`) inicializado;
- ambiente com timezone `America/Sao_Paulo` (padrÃ£o do projeto).

### 3.2 Edge (Dispositivo)
PrÃ©-requisitos:
- firmware compilado com `reservatorio_id`, `ponto_tipo` e `device_id` corretos;
- endpoint do backend acessÃ­vel na rede;
- token igual ao configurado no servidor.

## 4. InicializaÃ§Ã£o do Backend
No diretÃ³rio do projeto:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install django
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

ObservaÃ§Ãµes:
- em produÃ§Ã£o, usar variÃ¡veis de ambiente para `DJANGO_SECRET_KEY` e `ESP32_API_TOKEN`;
- evitar `DEBUG=True` fora de ambiente local.

## 5. Acesso e Fluxo BÃ¡sico na UI
Fluxo padrÃ£o:
1. Acessar `/entrar/` com usuÃ¡rio vÃ¡lido.
2. Ir para dashboard (`/`) e verificar cards dos reservatÃ³rios.
3. Selecionar perÃ­odo (`15m` atÃ© `90d`) conforme janela de anÃ¡lise.
4. Abrir detalhe do reservatÃ³rio para investigaÃ§Ã£o de sÃ©rie temporal.

## 6. Rotina DiÃ¡ria de OperaÃ§Ã£o
Checklist diÃ¡rio recomendado:
1. Verificar se hÃ¡ reservatÃ³rios sem dados recentes.
2. Conferir status geral (`bom`, `atencao`, `perigo`) por card.
3. Comparar tendÃªncias antes/depois tratamento.
4. Abrir detalhes de casos em `atencao`/`perigo`.
5. Registrar aÃ§Ãµes tomadas (operaÃ§Ã£o, limpeza, recalibraÃ§Ã£o).

## 7. InterpretaÃ§Ã£o Operacional de Status
ConvenÃ§Ã£o:
- `bom`: valores dentro da faixa esperada;
- `atencao`: desvio moderado de uma ou mais mÃ©tricas;
- `perigo`: desvio crÃ­tico de uma ou mais mÃ©tricas.

Regra do reservatÃ³rio:
- status geral reflete exclusivamente o ponto `depois_tratamento`.

ImplicaÃ§Ã£o operacional:
- ponto `antes_tratamento` Ã© diagnÃ³stico do afluente;
- ponto `depois_tratamento` direciona aÃ§Ã£o de qualidade entregue.

## 8. OperaÃ§Ã£o do Módulo Edge em Campo
### 8.1 Startup do Dispositivo
Passos:
1. Energizar ESP32.
2. Aguardar conexÃ£o em modo AP ou STA.
3. Confirmar inÃ­cio de ciclo de leitura.
4. Validar chegada de dados no backend.

### 8.2 ValidaÃ§Ã£o Inicial de ComunicaÃ§Ã£o
CritÃ©rios:
- `POST /api/esp32/leituras/` retorna `201`;
- dashboard atualiza leitura no reservatÃ³rio correto;
- `device_id` aparece nos `sinais_brutos` quando enviado.

## 9. OperaÃ§Ã£o da Plataforma (Dashboard e Detalhe)
### 9.1 Dashboard
FunÃ§Ãµes operacionais:
- visÃ£o consolidada de todos reservatÃ³rios;
- comparaÃ§Ã£o de mÃ©dias prÃ©/pÃ³s por perÃ­odo selecionado;
- filtro por nome ou status.

### 9.2 Detalhe do ReservatÃ³rio
FunÃ§Ãµes operacionais:
- status separado por ponto antes/depois;
- Ãºltimas mediÃ§Ãµes por mÃ©trica;
- grÃ¡ficos histÃ³ricos (temperatura, TDS, turbidez, pH);
- ediÃ§Ã£o das faixas de referÃªncia.

## 10. OperaÃ§Ã£o de SessÃµes de CalibraÃ§Ã£o
Fluxo resumido:
1. Abrir `Calibrar` no detalhe.
2. Selecionar ponto (`antes` ou `depois`).
3. Selecionar sensor.
4. Iniciar sessÃ£o.
5. Aguardar estabilidade.
6. Confirmar calibraÃ§Ã£o.
7. Encerrar sessÃ£o quando concluÃ­do.

Durante sessÃ£o:
- ESP32 envia amostras para endpoint dedicado;
- UI atualiza polling a cada 5 segundos;
- botÃµes sÃ£o habilitados somente com estabilidade mÃ­nima.

## 11. Rotina Semanal Recomendada
Checklist semanal:
1. revisar reservatÃ³rios com maior incidÃªncia de `atencao/perigo`;
2. validar tendÃªncia de mÃ©dias por perÃ­odo mais amplo (7d/15d/30d);
3. revisar sensores com calibraÃ§Ã£o vencida;
4. avaliar consistÃªncia entre ponto antes e depois;
5. revisar logs de falha de comunicaÃ§Ã£o dos dispositivos.

## 12. GestÃ£o de Incidentes
### 12.1 Incidente: sem dados no dashboard
Procedimento:
1. confirmar backend online;
2. validar rota `/api/esp32/leituras/`;
3. validar token;
4. verificar conectividade Wi-Fi do ESP32;
5. checar se fila offline estÃ¡ sendo drenada apÃ³s retorno da rede.

### 12.2 Incidente: dados com oscilaÃ§Ã£o alta
Procedimento:
1. inspecionar fisicamente os sensores;
2. verificar estabilidade elÃ©trica;
3. conferir necessidade de recalibraÃ§Ã£o;
4. revisar parÃ¢metros de amostragem no firmware;
5. comparar comportamento em ponto antes/depois.

### 12.3 Incidente: erro 401 na API
Procedimento:
1. conferir `ESP32_API_TOKEN` no servidor;
2. conferir token no firmware;
3. reiniciar backend apÃ³s alteraÃ§Ã£o de variÃ¡vel de ambiente;
4. revalidar envio de leitura.

### 12.4 Incidente: erro 400 na API
Procedimento:
1. validar payload JSON;
2. conferir `reservatorio_id` e `ponto_tipo`;
3. conferir presenÃ§a de campos obrigatÃ³rios;
4. validar formato do bloco `raw`.

## 13. GovernanÃ§a Operacional
PrÃ¡ticas recomendadas:
- padronizar identificadores (`device_id`) por ponto fÃ­sico;
- manter registro de intervenÃ§Ãµes em sensores;
- versionar firmware e backend com rastreabilidade;
- manter janela de manutenÃ§Ã£o planejada para atualizaÃ§Ã£o.

## 14. SeguranÃ§a Operacional
Regras mÃ­nimas:
1. nÃ£o expor token em documentos pÃºblicos;
2. nÃ£o manter token default em produÃ§Ã£o;
3. restringir acesso administrativo ao backend;
4. segmentar rede de dispositivos IoT;
5. aplicar backup regular do banco.

## 15. Backup e RecuperaÃ§Ã£o
Para ambiente SQLite:
- realizar cÃ³pia periÃ³dica do arquivo `db.sqlite3`;
- guardar snapshots com data/hora e ambiente;
- testar restauraÃ§Ã£o em ambiente de homologaÃ§Ã£o.

## 16. Indicadores Operacionais Sugeridos
KPIs recomendados:
- taxa de sucesso de ingestÃ£o (`2xx / total`);
- quantidade de leituras por ponto por dia;
- tempo mÃ©dio em `atencao/perigo`;
- tempo mÃ©dio para normalizaÃ§Ã£o apÃ³s alerta;
- percentual de sensores com calibraÃ§Ã£o dentro do prazo.

## 17. CritÃ©rios de AceitaÃ§Ã£o da OperaÃ§Ã£o
A operaÃ§Ã£o diÃ¡ria Ã© considerada saudÃ¡vel quando:
1. leituras chegam continuamente nos dois pontos;
2. dashboard atualiza sem lacunas crÃ­ticas;
3. nÃ£o hÃ¡ filas offline represadas por longos perÃ­odos;
4. calibraÃ§Ãµes crÃ­ticas estÃ£o em dia;
5. incidentes sÃ£o registrados e encerrados com causa identificada.

## 18. Encerramento de Turno
Checklist de fechamento:
1. registrar reservatÃ³rios em anomalia;
2. registrar aÃ§Ãµes executadas (limpeza/calibraÃ§Ã£o/intervenÃ§Ã£o);
3. confirmar status de conectividade dos dispositivos;
4. sinalizar pendÃªncias para prÃ³ximo turno.





