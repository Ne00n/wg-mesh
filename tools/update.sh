cat targets.txt | while read dest;
do
  echo "Running $dest"
  ssh -n "$dest" su wg-mesh -c "cd; cd /opt/wg-mesh/; git config --global --add safe.directory /opt/wg-mesh"
  ssh -n "$dest" su wg-mesh -c "cd; cd /opt/wg-mesh/; git checkout experimental; git pull --ff-only;" < /dev/null
  ssh -n "$dest" systemctl restart wgmesh-bird
  ssh -n "$dest" systemctl restart wgmesh
done
