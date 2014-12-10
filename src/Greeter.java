public class Greeter {
        public static void main(String[] args) {
                Greeting greeting = new Greeting();
                GreetingThread threads[] = new GreetingThread[4];

                for(int i = 0; i < 4; ++i) {
                        threads[i] = new GreetingThread(greeting);
                        threads[i].start();
                }

                for(int i = 0; i < 4; ++i) {
                        try {
                                threads[i].join();
                        }
                        catch(InterruptedException ie) {
                        }
                }
        }
}

