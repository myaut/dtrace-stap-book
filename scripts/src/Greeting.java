public class Greeting {
        GreetingProvider provider;

        public Greeting(GreetingProvider provider) {
                this.provider = provider;
        }

        public void greet(int greetingId) {
                provider.greetingStart(greetingId);
                System.out.println("Hello DTrace!");
                provider.greetingEnd(greetingId);
        }
}

