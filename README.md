# campus-fetch (para campus.exactas.uba.ar)

### Cómo utilizarlo:

1) Copiar el archivo `secret.example.py` a `secret.py` y modificarlo siguiendo las instrucciones del mismo, agregando su DNI y contraseña del campus.

2) Obtener los ids y nombres de las materias de las cuáles quieren descargar el contenido. 
   
   Para saber el id sólo basta con entrar a la materia en el campus y revisar el final de su url:
    https://campus.exactas.uba.ar/course/view.php?id=ID_DE_LA_MATERIA

    (por ejemplo, el id de https://campus.exactas.uba.ar/course/view.php?id=3752 sería 3752)

    Luego su nombre es cómo esta descripta en el campus, pueden revisar lo que dice debajo de "Curso Actual". 

    En la URL de ejemplo su nombre es "isoftcont-2023-c1". 

3) Una vez que obtuvieron los ids y nombres de las materias deben agregarlos a la lista `MATERIAS` del archivo `config.py` con el mismo formato que el ejemplo. 

4) Por último sólo queda pararse sobre el directorio "/campus_fetch" (probar usando WSL en caso de Windows) y correr:

        make

5) Luego de correr el script se van a descargar todos los archivos de las materias que agregaron al *config.py* en una carpeta "downloads".

6) (opcional) Comenzar a preparar el final que venís colgando :)
