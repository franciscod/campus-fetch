# Campus Fetch

# Cómo utilizarlo:

1) Modificar el archivo *secret.example.py* siguiendo las instrucciones del mismo, agregando su DNI y contraseña. (no se olviden de copiarlo y renombrarlo cómo *secret.py* )
2) Obtener los ids y nombres de las materias de las cuáles quieren descargar el contenido. Para saber el id sólo basta con entrar a la materia en el campus y revisar su url:
[https://campus.exactas.uba.ar/course/view.php?id=ID_DE_LA_MATERIA] ([https://campus.exactas.uba.ar/course/view.php?id=3752])
Luego su nombre es cómo esta descripta en el campus, pueden revisar lo que dice debajo de "Curso Actual". En la URL de ejemplo su nombre es "isoftcont-2023-c1". 
3) Una vez que obtuvieron los ids y nombres de las materias deben agregarlos a la lista **Materias** del archivo *config.py* con el mismo formato que el ejemplo. 
4) Por último si tienen WSL o Linux sólo queda pararse sobre el directorio "/campus_fetch" y correr:

```bash
make
```

5) Luego de correr el script se van a descargar todos los archivos de las materias que agregaron al *config.py* en una carpeta "\donwloads".
(opcional) 6) Comenzar a preparar el final que venís colgando :)

