#include <pthread.h>

#include <stdlib.h>
#include <stdio.h>

#define NUM_CONSUMERS   4
#define NUM_REQUESTS    42

#define TM_CONSUMER_LOCKED  100000
#define TM_CONSUMER_FREE    400000
#define TM_REPORTER        1000000
#define TM_PRODUCER         150000

/* Если установить этот флаг в 0, потоки остановятся */
int working = 1;

/* Маска занятых потоков-потребителей и выполненных ими запросов */
pthread_rwlock_t stat_lock;
unsigned busy_consumers = 0;
unsigned requests = 0;

/* Условная переменная для уведомления потоков-потребителей */
pthread_mutex_t mutex;
pthread_cond_t cond;

/* Поток-потребитель — "исполняет" поступающие запросы */
void* consumer_thread(void* arg) {
    int cid = (int) arg;
    
    while(working) {
        pthread_mutex_lock(&mutex);
        pthread_cond_wait(&cond, &mutex);
        pthread_mutex_unlock(&mutex);
        
        pthread_rwlock_wrlock(&stat_lock);
        busy_consumers |= 1 << cid;
        pthread_rwlock_unlock(&stat_lock);
        
        /* Начало обработки запроса */
        
        pthread_mutex_lock(&mutex);
        usleep(TM_CONSUMER_LOCKED);
        pthread_mutex_unlock(&mutex);
        usleep(TM_CONSUMER_FREE);
        
        /* Окончание обработки запроса */
        
        pthread_rwlock_wrlock(&stat_lock);
        busy_consumers &= ~(1 << cid);
        ++requests;
        pthread_rwlock_unlock(&stat_lock);
    }
    
    return (void*) cid;
}

/* Поток, печатающий маску занятых потоков-потребителей */
void* reporter_thread(void* arg) {
    unsigned busy_consumers_intl = 0;
    unsigned requests_intl = 0;
    
    time_t t;
    
    while(working) {
        pthread_rwlock_rdlock(&stat_lock);
        busy_consumers_intl = busy_consumers;
        requests_intl = requests;
        pthread_rwlock_unlock(&stat_lock);
        
        t = time(NULL);
        printf("%24s %-8x %-8d\n", ctime(&t), busy_consumers_intl, requests_intl);
        
        usleep(TM_REPORTER);
    }
    
    return NULL;
}  

/* Главный поток -- инициаилизирует/удаляет pthread-объекты, 
 * также выполняет роль потока-производителя */
int main() {
   pthread_t consumers[NUM_CONSUMERS];
   pthread_t reporter;
   void* result;
   int i;
   unsigned busy_consumers_intl = 0;
   const unsigned consumers_mask = ((1 << NUM_CONSUMERS) - 1);
   
   /* Инициализируем pthread-объекты */
   pthread_rwlock_init(&stat_lock, NULL);
   pthread_mutex_init(&mutex, NULL);
   pthread_cond_init(&cond, NULL);
   
   for(i = 0; i < NUM_CONSUMERS; ++i) {
       pthread_create(consumers + i, NULL, consumer_thread, (void*) i);
   }
   pthread_create(&reporter, NULL, reporter_thread, NULL);
   
   for(i = 0; i < NUM_REQUESTS; ++i) {
       /* Создание запроса */
       
       /* Если все потребители заняты - ждем с опросом */
       while(busy_consumers_intl == consumers_mask) {
            pthread_rwlock_rdlock(&stat_lock);
            busy_consumers_intl = busy_consumers;
            pthread_rwlock_unlock(&stat_lock);        
            usleep(TM_PRODUCER / NUM_CONSUMERS);
       }
       
       /* Отправка запроса одному из потребителей */       
       pthread_mutex_lock(&mutex);
       pthread_cond_signal(&cond);
       pthread_mutex_unlock(&mutex);
       
       usleep(TM_PRODUCER);
       
       busy_consumers_intl = 0;
   }
   
   /* Сбрасываем флаг working чтобы все потоки завершили свое исполнение */
   working = 0;
   
   /* Уведомляем потоки потребителей */
   pthread_mutex_lock(&mutex);
   pthread_cond_broadcast(&cond);
   pthread_mutex_unlock(&mutex);
   
   /* Уничтожаем pthread-объекты */
   for(i = 0; i < NUM_CONSUMERS; ++i) {
       pthread_join(consumers[i], &result);
   } 
   pthread_join(reporter, &result);
   
   pthread_mutex_destroy(&mutex);
   pthread_cond_destroy(&cond);   
   pthread_rwlock_destroy(&stat_lock);
   
   printf("Total requests = %d\n", requests);
   
   return 0;
}

