import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AmbientBackground } from "@/components/layout/ambient-background";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function AuthPage() {
  const { login, register } = useAuth();
  const [loading, setLoading] = useState(false);

  async function onLogin(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setLoading(true);
    try {
      await login(String(fd.get("username")), String(fd.get("password")));
      toast.success("Welcome back");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  }

  async function onRegister(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setLoading(true);
    try {
      await register(String(fd.get("username")), String(fd.get("email")), String(fd.get("password")));
      toast.success("Account created — sign in with your credentials");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-10">
      <AmbientBackground />

      <div className="relative z-10 w-full max-w-[420px] animate-slide-up">
        <div className="glass-strong p-8 sm:p-10">
          <p className="brand-mark mb-8 text-center text-3xl">
            Con<span>ductor</span>
          </p>

          <Tabs defaultValue="login">
            <TabsList className="mb-6 w-full">
              <TabsTrigger value="login" className="flex-1">
                Sign in
              </TabsTrigger>
              <TabsTrigger value="register" className="flex-1">
                Register
              </TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <form onSubmit={onLogin} className="space-y-5">
                <div>
                  <Label htmlFor="login-username">Username</Label>
                  <Input
                    id="login-username"
                    name="username"
                    autoComplete="username"
                    placeholder="your username"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="login-password">Password</Label>
                  <Input
                    id="login-password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="••••••••"
                    required
                  />
                </div>
                <Button type="submit" className="w-full" size="lg" disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                  Sign in
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register">
              <form onSubmit={onRegister} className="space-y-5">
                <div>
                  <Label htmlFor="reg-username">Username</Label>
                  <Input id="reg-username" name="username" autoComplete="username" required />
                </div>
                <div>
                  <Label htmlFor="reg-email">Email</Label>
                  <Input id="reg-email" name="email" type="email" autoComplete="email" required />
                </div>
                <div>
                  <Label htmlFor="reg-password">Password</Label>
                  <Input
                    id="reg-password"
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    required
                  />
                </div>
                <Button type="submit" className="w-full" size="lg" disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : null}
                  Create account
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
