import com.sun.tracing.*;

public class JSDT {
   static public void main(String[] args) {
       ProviderFactory providerFactory = 
		new sun.tracing.dtrace.DTraceProviderFactory();
       GreetingProvider greetingProvider = (GreetingProvider) 
            providerFactory.createProvider(GreetingProvider.class);

       Greeting greeter = new Greeting(greetingProvider);

       for(int id = 0; id < 100; ++id) {
            greeter.greet(id);

            try { Thread.sleep(500); }
            catch(InterruptedException ie) {}
       }

       greetingProvider.dispose();
   }
}

