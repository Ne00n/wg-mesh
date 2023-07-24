cat targets.txt | while read dest;
do
  echo "Running $dest"
  ssh $dest <<EOF
su wg-mesh
cd
timeout 5 git pull --ff-only
exit
systemctl restart wgmesh
systemctl restart wgmesh-bird
EOF
done