cat targets.txt | while read dest;
do
  echo "Running $dest"
  ssh -n "$dest" su wg-mesh -c "cd; cd /opt/wg-mesh/; git checkout experimental; git pull;" < /dev/null
  ssh -n "$dest" "systemctl restart wgmesh-bird" < /dev/null
done
