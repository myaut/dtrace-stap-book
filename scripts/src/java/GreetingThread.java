class GreetingThread extends Thread {
         Greeting greeting;

         GreetingThread(Greeting greeting) {
             this.greeting = greeting;
             super.setDaemon(true);
         }

         public void run() {
             while(true) {
                        greeting.greet();
                        try {
                                Thread.sleep(1000);
                        } catch (InterruptedException e) {
                        }
             }
         }
}

