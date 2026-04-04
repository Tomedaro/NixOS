<<<<<<< HEAD
{...}: {
=======
{ ... }:
{
>>>>>>> upstream/master
  services.auto-cpufreq = {
    enable = true;
    settings = {
      charger = {
        governor = "performance";
        turbo = "auto";
      };
      battery = {
        governor = "schedutil";
<<<<<<< HEAD
        scaling_max_freq = 3800000;
=======
>>>>>>> upstream/master
        turbo = "never";
      };
    };
  };
}
