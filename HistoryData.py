import pandas as pd
import soccerdata as scdat
import os 

sfscore = scdat.Sofascore()
ligas = sfscore.read_leagues()
print(ligas)
quit()


# Importar la clase
sofascore = sd.Sofascore(leagues="ESP-La Liga", seasons="2022/2023")


print("Class method")
league_table = sofascore.read_league_table()
league_table. info()
league_table.head()


schedule = sofascore.read_schedule()
schedule.info()
schedule.head()



#ruta = r"C:\Users\USUARIO\Desktop\Futbol_xlsx\prueba.xlsx"
#league_table.to_excel(ruta, index=False)
#print("Descargo el excel en la ruta")