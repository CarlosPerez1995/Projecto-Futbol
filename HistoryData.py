import pandas as pd
import soccerdata as scdat
import os 
from pathlib import Path
sfscore = scdat.Sofascore()

ligas = sfscore.read_leagues()
# ligas.info()

# print(ligas)


sfscore = scdat.Sofascore("ENG-Premier League")
temporadas = sfscore.read_seasons()
# temporadas.info()

# print(temporadas)

sfscore = scdat.Sofascore("ENG-Premier League", ["2425","2526"])
Posiciones = sfscore.read_league_table()
# Posiciones.info()
# print(Posiciones)

sfscore = scdat.Sofascore("ENG-Premier League", ["2425","2526"])
Calendario = sfscore.read_schedule()
Calendario["date"] = pd.to_datetime(Calendario["date"], errors= "coerce").dt.tz_localize(None)
# Calendario.info()
# quit()
# print(Calendario)

path = r"C:\Users\USUARIO\Desktop\Futbol_xlsx"
# ligas.to_excel(f"{path}\Ligas.xlsx", index= True)

# temporadas.to_excel(f"{path}\Temporadas.xlsx", index= True)
# Posiciones.to_excel(f"{path}\Posiciones.xlsx", index= True)
Calendario.to_excel(f"{path}\Calendario.xlsx", index= True)
quit()


