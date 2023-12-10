# Foodgram: deployment instructions 

Clone project to server 
```
git@github.com:frailtynine/foodgram-project-react.git
```
Build frontend (Docker should be installed):
```
cd infra
```
```
sudo docker compose up
```
A `build` folder will appear. Don't forget to bring frontend server down, you won't need it anymore. 

Create .env file in the root folder of the project: 

Fill it with database data: 
```
POSTGRES_DB=db_name
POSTGRES_USER=db_user
POSTGRES_PASSWORD=db_password
DB_NAME=db_name
DB_HOST=db_host 
DB_PORT=5432
```
Add settings.py secrets: `SECRET_KEY`, `DEBUG` (empty value resolves to False) and `ALLOWED_HOSTS` (separated by space). 

Start the project: 
```sudo docker compose -f docker-compose.production.yml -d
```
Inside foodgram_backend container run migrations, load database with recipes, create superuser, collect and copy static:
```
python manage.py makemigrations
python manage.py migrate
python manage.py load_db
python manage.py createsuperuser
python manage.py collectstatic
cp -r collected_static/. /static/static/
```

Profit! 

# praktikum_new_diplom
URL: foodgram-practicum.ddns.net

username: alex@ya.ru
email: alex@ya.ru
password: Admin12345

# Комментарии для ревьюера 

Я не понял, в чем была проблема с данными отсюда. Вероятно, в качестве логина в админке использовалась почта, но почта используется для логина во фронте, а в админке это username, и никаких требований переопределять это в ТЗ не было. На всякий случай теперь юзернейм и почта одинаковые. 

Не понял, где допускается регистрация пользователя с пустым именем или фамилией. Ни на фронте, ни через api вручную этого у меня сделать не получилось. Предположил, что речь шла об админке, переопределил формы создания и редактирования пользователей. 

