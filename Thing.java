
interface Stuff {
    void run(double x);
}

public class Thing {

    int test;

    public static void main(String[] args) {
        System.out.println("Hello, World!");
        Thing t = new Thing();
        t.test = 12;
        System.out.println(t.hmmm(t).test);
        System.out.println(5.0);
    }

    public Thing hmmm(Thing other) {
        return other;
    }
}
