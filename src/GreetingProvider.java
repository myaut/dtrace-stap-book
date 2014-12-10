import com.sun.tracing.Provider;

public interface GreetingProvider extends Provider {
        public void greetingStart(int greetingId); 
        public void greetingEnd(int greetingId);
}

